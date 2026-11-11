"""Variable LM Studio placement with fake lms/nvidia-smi; no model is loaded."""

import json

import subprocess

import tempfile

import unittest

from pathlib import Path

from gurumoji.services.ai.lmstudio_placement import (

    LMStudioPlacement, Placement, choose, keep_current, required_context,

)

# lms --estimate-only figures measured on an RTX 5070 (12 GiB) for gemma-4-12b.

ESTIMATES = {("max", 16384): 9.74, ("max", 20480): 10.36, ("max", 32768): 12.23,

             ("0.95", 32768): 11.7, ("0.9", 32768): 11.25, ("0.85", 32768): 10.76,

             ("0.8", 32768): 10.27}  # 0.8 is interpolated

class FakeLMStudio:

    def __init__(self, loaded=None, used_mib=700, total_mib=12227):

        self.loaded, self.used, self.total, self.commands = loaded, used_mib, total_mib, []

    def run(self, args, **kwargs):

        self.commands.append(args[1:] if args[0] != "nvidia-smi" else ["nvidia-smi"])

        if args[0] == "nvidia-smi":

            return subprocess.CompletedProcess(args, 0, f"{self.total}, {self.used}\n", "")

        if args[1] == "unload":

            self.loaded = None

            return subprocess.CompletedProcess(args, 0, "", "")

        gpu, context = args[args.index("--gpu") + 1] if "--gpu" in args else "auto", int(args[args.index("-c") + 1])

        if "--estimate-only" in args:

            # lms writes its estimate report on stderr.

            return subprocess.CompletedProcess(args, 0, "", f"Estimated GPU Memory:   {ESTIMATES.get((gpu, context), 99)} GiB\n")

        self.loaded = context

        return subprocess.CompletedProcess(args, 0, "", "")

    def fetch(self, url):

        instances = [{"config": {"context_length": self.loaded}}] if self.loaded else []

        return {"models": [{"key": "m", "loaded_instances": instances}]}

class PlacementTests(unittest.TestCase):

    def manager(self, fake, folder):

        return LMStudioPlacement(lms="lms", endpoint="http://127.0.0.1:1234", state_path=Path(folder) / "state.json",

                                 run=fake.run, fetch=fake.fetch)

    def test_required_context_is_the_smallest_step_with_a_margin(self):

        self.assertEqual(required_context(9000, 4096), 16384)

        self.assertEqual(required_context(16000, 4096), 24576)

        self.assertEqual(required_context(24576, 4096), 32768)

        with self.assertRaises(ValueError):

            required_context(30000, 4096)

    def test_choose_takes_the_most_offload_that_fits(self):

        estimate = lambda gpu, context: ESTIMATES.get((gpu, context), 99)

        self.assertEqual(choose(16384, 10.5, estimate), Placement(16384, "max", 9.74))

        self.assertEqual(choose(32768, 10.9, estimate), Placement(32768, "0.85", 10.76))

        self.assertEqual(choose(16384, None, estimate), Placement(16384, "auto", None))

        with self.assertRaises(RuntimeError):

            choose(32768, 5.0, estimate)

    def test_keep_only_a_large_enough_instance_that_is_already_fast(self):

        self.assertTrue(keep_current(16384, {"context": 16384, "gpu": "max"}, 16384, Placement(16384, "max", None)))

        self.assertTrue(keep_current(32768, {"context": 32768, "gpu": "max"}, 16384, Placement(16384, "max", None)))

        self.assertFalse(keep_current(16384, {"context": 16384, "gpu": "max"}, 32768, Placement(32768, "0.85", None)))

        self.assertFalse(keep_current(32768, None, 16384, Placement(16384, "max", None)))  # unknown offload

        self.assertFalse(keep_current(32768, {"context": 32768, "gpu": "0.85"}, 16384, Placement(16384, "max", None)))

    def test_short_task_reloads_an_unknown_long_instance_fully_on_the_gpu(self):

        fake = FakeLMStudio(loaded=32768)

        with tempfile.TemporaryDirectory() as folder:

            report = self.manager(fake, folder).ensure("m", 9000, 4096)

            self.assertEqual((report["action"], report["context"], report["gpu"]), ("loaded", 16384, "max"))

            self.assertEqual(fake.commands[0], ["unload", "m"])

            self.assertEqual(fake.commands[1], ["nvidia-smi"])  # measured after unloading

            self.assertIn(["load", "m", "--gpu", "max", "-c", "16384", "--identifier", "m", "-y"], fake.commands)

            self.assertEqual(json.loads((Path(folder) / "state.json").read_text(encoding="utf-8"))["m"]["gpu"], "max")

            fake.commands.clear()

            again = self.manager(fake, folder).ensure("m", 8000, 4096)

            self.assertEqual(again["action"], "kept")

            self.assertEqual(fake.commands, [])  # no measurement or reload when already ideal

    def test_long_task_grows_the_context_and_trades_offload(self):

        fake = FakeLMStudio(loaded=16384)

        with tempfile.TemporaryDirectory() as folder:

            (Path(folder) / "state.json").write_text(json.dumps({"m": {"context": 16384, "gpu": "max"}}), encoding="utf-8")

            report = self.manager(fake, folder).ensure("m", 20000, 4096)

            # 10.46 GiB free after headroom: 0.85 (10.76) does not fit, 0.8 does.

            self.assertEqual((report["context"], report["gpu"], report["estimate_gib"]), (32768, "0.8", 10.27))

            self.assertAlmostEqual(report["budget_gib"], (12227 - 700) / 1024 - 0.8)

    def test_a_failed_measurement_still_reloads_with_lmstudio_placement(self):

        fake = FakeLMStudio(loaded=32768)

        original = fake.run

        def broken(args, **kwargs):

            if "--estimate-only" in args:

                return subprocess.CompletedProcess(args, 0, "", "unexpected report")

            return original(args, **kwargs)

        fake.run = broken

        with tempfile.TemporaryDirectory() as folder:

            report = self.manager(fake, folder).ensure("m", 9000, 4096)

        self.assertEqual((report["action"], report["gpu"], report["placement_failure"]),

                         ("loaded_with_lmstudio_placement", "auto", "RuntimeError"))

        self.assertEqual(fake.loaded, 16384)

        self.assertIn(["load", "m", "-c", "16384", "--identifier", "m", "-y"], fake.commands)

    def test_a_load_that_does_not_give_the_context_is_an_error(self):

        fake = FakeLMStudio(loaded=None)

        original = fake.run

        def short(args, **kwargs):

            done = original(args, **kwargs)

            if args[1:2] == ["load"] and "--estimate-only" not in args:

                fake.loaded = 8192

            return done

        fake.run = short

        with tempfile.TemporaryDirectory() as folder, self.assertRaises(RuntimeError):

            self.manager(fake, folder).ensure("m", 9000, 4096)

if __name__ == "__main__":

    unittest.main()

