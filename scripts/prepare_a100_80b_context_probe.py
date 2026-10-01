"""Build a synthetic 8K/16K context sweep for the pinned Qwen3-Next 80B probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import prepare_a100_80b_probe as base


CONTEXT_SWEEP = r'''    expected_claim = '架空の記録では、確認できない値は「不明」とする。'
    system_prompt = (
        'This is a synthetic context-capacity check. Use only the repeated synthetic records. '
        'Return exactly one JSON object with keys claim and evidence_id. '
        'Copy the claim exactly and set evidence_id to SYNTHETIC-1.'
    )
    record_line = ('claim: ' + expected_claim + ' evidence_id: SYNTHETIC-1.\n')
    max_output_tokens = 64
    target_fraction = 0.75

    def messages_for(repetitions):
        user_content = record_line * repetitions + '\nReturn the claim and evidence ID now.'
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content},
        ]
        return messages, user_content

    def token_count_for(repetitions):
        messages, _ = messages_for(repetitions)
        templated = local_http.post(
            f'http://127.0.0.1:{SERVER_PORT}/apply-template',
            json={'messages': messages}, timeout=60,
        )
        templated.raise_for_status()
        prompt_text = templated.json()['prompt']
        tokenized = local_http.post(
            f'http://127.0.0.1:{SERVER_PORT}/tokenize',
            json={'content': prompt_text, 'add_special': True}, timeout=60,
        )
        tokenized.raise_for_status()
        return len(tokenized.json()['tokens'])

    previous_status = 'not_run'
    for context_length in (8192, 16384):
        stage = {
            'context_length': context_length,
            'gpu_layers_requested': GPU_LAYERS,
            'status': 'running',
            'started_at': datetime.now(timezone.utc).isoformat(),
        }
        stage_started = time.monotonic()
        server = None
        server_log = None
        sampler = None
        gpu_samples.clear()
        stop_sampling = threading.Event()
        try:
            server_log = (SOURCE_ROOT / f'llama_server_{context_length}.log').open('wb')
            server = subprocess.Popen([
                str(binary), '-m', str(model_path), '--host', '127.0.0.1',
                '--port', str(SERVER_PORT), '--alias', MODEL_REPO,
                '--jinja', '-ngl', str(GPU_LAYERS), '-c', str(context_length),
                '-np', '1',
            ], stdout=server_log, stderr=subprocess.STDOUT)
            load_started = time.monotonic()
            sampler = threading.Thread(target=sample_gpu, daemon=True)
            sampler.start()
            ready = False
            while time.monotonic() - load_started < min(600, remaining()):
                if server.poll() is not None:
                    raise RuntimeError('llama-server exited during model load')
                try:
                    response = local_http.get(f'http://127.0.0.1:{SERVER_PORT}/health', timeout=3)
                    if response.status_code == 200:
                        ready = True
                        break
                except requests.RequestException:
                    pass
                time.sleep(3)
            if not ready:
                raise TimeoutError(f'{context_length} context model did not become ready within 10 minutes')
            stage['model_load_seconds'] = round(time.monotonic() - load_started, 2)
            stage['gpu_memory_after_load'] = gpu_memory_mib()
            if stage['gpu_memory_after_load']['free_mib'] < 4_096:
                raise RuntimeError('model loaded without enough GPU headroom for inference')

            target_prompt_tokens = int(context_length * target_fraction)
            max_prompt_tokens = context_length - max_output_tokens - 128
            low = 0
            high = 1
            high_tokens = token_count_for(high)
            while high_tokens < target_prompt_tokens and high < 100_000:
                low = high
                high *= 2
                high_tokens = token_count_for(high)
            if high_tokens <= target_prompt_tokens:
                low = high
            else:
                while low + 1 < high:
                    middle = (low + high) // 2
                    middle_tokens = token_count_for(middle)
                    if middle_tokens <= target_prompt_tokens:
                        low = middle
                    else:
                        high = middle
            repetitions = max(1, low)
            measured_prompt_tokens = token_count_for(repetitions)
            if measured_prompt_tokens > max_prompt_tokens:
                raise RuntimeError('tokenized prompt leaves too little room for output')
            messages, user_content = messages_for(repetitions)
            stage['target_prompt_tokens'] = target_prompt_tokens
            stage['prompt_tokens_before_inference'] = measured_prompt_tokens
            stage['prompt_utilization'] = round(measured_prompt_tokens / context_length, 4)
            stage['synthetic_record_repetitions'] = repetitions
            stage['prompt_characters'] = len(user_content)
            stage['max_output_tokens'] = max_output_tokens

            inference_started = time.monotonic()
            response = local_http.post(
                f'http://127.0.0.1:{SERVER_PORT}/v1/chat/completions',
                json={
                    'model': MODEL_REPO,
                    'messages': messages,
                    'temperature': 0,
                    'max_tokens': max_output_tokens,
                    'stream': False,
                }, timeout=min(600, remaining()),
            )
            response.raise_for_status()
            body = response.json()
            content = body['choices'][0]['message']['content']
            stage['inference_seconds'] = round(time.monotonic() - inference_started, 2)
            stage['usage'] = body.get('usage')
            stage['timings'] = body.get('timings')
            stage['synthetic_response'] = content[:1_000]
            try:
                parsed = json.loads(content)
                stage['json_valid'] = isinstance(parsed, dict) and set(parsed) == {'claim', 'evidence_id'}
                stage['evidence_id_valid'] = stage['json_valid'] and parsed['evidence_id'] == 'SYNTHETIC-1'
                stage['claim_matches_fixture'] = stage['json_valid'] and parsed['claim'] == expected_claim
            except (ValueError, TypeError):
                stage['json_valid'] = False
                stage['evidence_id_valid'] = False
                stage['claim_matches_fixture'] = False
            stage['gpu_memory_after_inference'] = gpu_memory_mib()
            stage['status'] = (
                'passed' if stage['json_valid'] and stage['evidence_id_valid']
                else 'inference_quality_failed'
            )
        except Exception as exc:
            stage['status'] = 'failed'
            stage['error_type'] = type(exc).__name__
            stage['error_summary'] = str(exc)[:400]
        finally:
            stop_sampling.set()
            if sampler is not None:
                sampler.join(timeout=3)
            if server is not None:
                server.terminate()
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=10)
            if server_log is not None:
                server_log.close()
            stage['peak_gpu_memory_mib'] = max(gpu_samples) if gpu_samples else None
            stage['elapsed_seconds'] = round(time.monotonic() - stage_started, 2)
            stage['ended_at'] = datetime.now(timezone.utc).isoformat()
            result['context_sweep'].append(stage)
            result['status'] = 'running'
            checkpoint = Path('/content') / RESULT_NAME
            checkpoint.write_text(
                json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')),
                encoding='utf-8',
            )
            print('CONTEXT_STAGE', json.dumps(stage, ensure_ascii=False), flush=True)
        previous_status = stage['status']
        if context_length == 8192 and previous_status != 'passed':
            break
    result['status'] = (
        'passed' if len(result['context_sweep']) == 2 and
        all(stage['status'] == 'passed' for stage in result['context_sweep'])
        else 'partial_failed'
    )
'''


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"expected one {label} block, found {count}")
    return source.replace(old, new, 1)


def build_context_notebook(folder_id: str) -> dict:
    notebook = base.build_notebook(folder_id)
    code_cell = next(cell for cell in notebook['cells'] if cell.get('cell_type') == 'code')
    code = ''.join(code_cell['source'])
    code = replace_once(
        code,
        "RESULT_NAME = f'Gurumoji_A100_80B_Probe_{RUN_ID}.json'",
        "RESULT_NAME = f'Gurumoji_A100_80B_Context_Probe_{RUN_ID}.json'",
        'result file name',
    )
    code = replace_once(
        code,
        "    'gpu_layers_requested': GPU_LAYERS,\n    'synthetic_input_only': True,\n    'steps': [],",
        "    'gpu_layers_requested': GPU_LAYERS,\n    'context_lengths_tested': [8192, 16384],\n"
        "    'context_sweep': [],\n    'synthetic_input_only': True,\n    'steps': [],",
        'result context fields',
    )
    start = "    server_log = (SOURCE_ROOT / 'llama_server.log').open('wb')\n"
    end = (
        "    result['status'] = ('passed' if result['json_valid'] and\n"
        "                        result['evidence_id_valid'] else 'inference_quality_failed')"
    )
    start_index = code.find(start)
    end_index = code.find(end, start_index)
    if start_index < 0 or end_index < 0:
        raise ValueError('could not find original inference section')
    end_index += len(end)
    code = code[:start_index] + CONTEXT_SWEEP.rstrip() + code[end_index:]
    compile(code, 'Gurumoji_A100_80B_Context_Probe.ipynb', 'exec')
    code_cell['source'] = code.splitlines(keepends=True)
    markdown = next(cell for cell in notebook['cells'] if cell.get('cell_type') == 'markdown')
    markdown['source'] = [
        '# Gurumoji A100 80B synthetic context sweep (8K and 16K)\n',
        'Select an A100 High RAM runtime and run all cells once. This checks GPU, host RAM, '
        'and disk, builds pinned CUDA llama.cpp, downloads and hash-checks the pinned Q4_K_M '
        'model, then tests synthetic prompts at 8K and 16K context with 30 GPU layers and '
        'the remaining layers in host RAM. Prompt length is measured with the model chat '
        'template and tokenizer; each test targets 75% of its context. The 16K stage runs '
        'only if the 8K stage passes. This measures capacity, latency, memory, and synthetic '
        'JSON behavior only; it does not process papers or create expert knowledge. The '
        'run has a 55-minute software budget and downloads a JSON result for later Drive upload.\n',
    ]
    return notebook


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder-id', default=base.DEFAULT_FOLDER_ID)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not args.folder_id or any(character in args.folder_id for character in "/\\?&#"):
        parser.error('folder ID is invalid')
    output = Path(args.output).resolve()
    if output.exists():
        parser.error('output Notebook already exists')
    output.parent.mkdir(parents=True, exist_ok=True)
    notebook = build_context_notebook(args.folder_id)
    output.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({
        'output': str(output),
        'model_repo': base.MODEL_REPO,
        'model_revision': base.MODEL_REVISION,
        'model_sha256': base.MODEL_SHA256,
        'llama_cpp_revision': base.LLAMA_CPP_REVISION,
        'context_lengths': [8192, 16384],
        'gpu_layers': 30,
        'synthetic_input_only': True,
    }, sort_keys=True))


if __name__ == '__main__':
    main()
