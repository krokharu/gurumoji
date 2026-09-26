"""Per-operation reasoning settings, kept explicit and isolated between jobs."""
STAGES = ("outline", "cleanup", "name_extract", "name_verify")
# ``auto`` remains valid for records created before the explicit thinking-mode UI.
# New jobs use either ``off`` or a concrete effort level.
LEVELS = ("auto", "off", "low", "medium", "high", "ultra")
SCHEMA_STAGES = {"meeting_outline": "outline", "transcript_outline_context": "outline",
                 # Insights are a long-form, evidence-grounded synthesis.  Reuse
                 # the outline control so local reasoning models can reserve
                 # generation tokens for the JSON findings.
                 "conversation_insights": "outline",
                 "transcript_cleanup": "cleanup", "transcript_recommended_cleanup": "cleanup",
                 "speaker_identity_extraction": "name_extract",
                 "speaker_identity_link_verification": "name_verify"}


STAGE_LABELS = {"outline": "会話の流れを整理", "cleanup": "文章の仕上げ",
                "name_extract": "話者名を確認", "name_verify": "話者を再確認"}
LEVEL_LABELS = {"auto": "自動", "off": "なし", "low": "低", "medium": "中", "high": "高", "ultra": "最大"}


def describe_efforts(value=None) -> str:
    """One line naming each stage's level, as the app's effort settings label them (CFG-04)."""
    efforts = normalize_efforts(value)
    return "、".join(f"{STAGE_LABELS[stage]}：{LEVEL_LABELS[efforts[stage]]}" for stage in STAGES)


def normalize_efforts(value=None):
    if value is None:
        return dict.fromkeys(STAGES, "auto")
    if not isinstance(value, dict) or set(value) - set(STAGES):
        raise ValueError("AIエフォートの設定形式が不正です。")
    result = {stage: value.get(stage, "auto") for stage in STAGES}
    if any(level not in LEVELS for level in result.values()):
        raise ValueError("AIエフォートは auto / off / low / medium / high / ultra を指定してください。")
    return result


def effort_payload(provider, model, schema_name, efforts=None):
    level = normalize_efforts(efforts).get(SCHEMA_STAGES.get(schema_name), "auto")
    if level == "auto":
        return {}
    if provider == "openai":
        return {"reasoning": {"effort": {"off": "none", "ultra": "xhigh"}.get(level, level)}}
    if provider == "lmstudio":
        return {"reasoning_effort": {"off": "none", "ultra": "xhigh"}.get(level, level)}
    if provider == "google":
        if model.startswith("gemini-2.5-"):
            budget = {
                "off": 0, "low": 1024, "medium": 8192, "high": 16384, "ultra": 24576,
            }[level]
            # Gemini 2.5 Pro does not support a zero thinking budget; its
            # lowest supported budget is the closest safe OFF equivalent.
            if level == "off" and model.startswith("gemini-2.5-pro"):
                budget = 1024
            return {"thinkingConfig": {"thinkingBudget": budget}}
        # Gemini 3 cannot fully disable thinking. MINIMAL is its closest supported
        # setting, and ultra maps to the provider's maximum HIGH setting.
        if level == "off":
            level = "minimal"
        elif level == "ultra":
            level = "high"
        if model.startswith("gemini-3-pro") and level == "medium":
            level = "high"
        return {"thinkingConfig": {"thinkingLevel": level.upper()}}
    return {}


def local_effort_payload(level, capability):
    """Map UI presets to values the local model actually supports."""
    if level == 'auto':
        return {}
    allowed = capability.get('allowed_options', [])
    # Gemma and Llama variants commonly expose no reasoning capability.  Do
    # not send an OpenAI-compatible parameter they cannot accept; generation
    # continues with the model's normal instruction mode.
    if not allowed:
        return {}
    if level == 'off' and 'off' in allowed:
        return {'reasoning_effort': 'none'}
    if level in allowed:
        return {'reasoning_effort': level}
    if level == 'ultra' and 'xhigh' in allowed:
        return {'reasoning_effort': 'xhigh'}
    # LM Studio model families do not all expose the same vocabulary.  These
    # fallbacks keep the UI's common scale usable for Qwen, Gemma, and Llama
    # derivatives that advertise minimal or xhigh instead of a direct level.
    aliases = {
        'low': ('minimal',),
        'medium': ('low', 'minimal'),
        'high': ('xhigh', 'medium', 'low', 'minimal'),
        'ultra': ('high', 'medium', 'low', 'minimal'),
    }
    for value in aliases.get(level, ()):
        if value in allowed:
            return {'reasoning_effort': value}
    if level in ('low', 'medium', 'high', 'ultra') and 'on' in allowed and capability.get('default') == 'on':
        return {}  # Binary thinking models have no effort distinction.
    raise ValueError('このローカルモデルでは指定のエフォートを使えません。思考モードをONにするか、対応する設定を選んでください。')
