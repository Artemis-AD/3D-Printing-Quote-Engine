"""Tests for Config disk reload, CONFIG_PATH, and atomic save."""
import json
import os
import tempfile
import unittest

from config import Config


class ConfigReloadTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.config_path = os.path.join(self._tmpdir.name, 'config.json')

    def _write_config(self, data, path=None, bump_mtime=False):
        path = path or self.config_path
        previous = os.path.getmtime(path) if os.path.exists(path) else None
        with open(path, 'w') as handle:
            json.dump(data, handle)
        if bump_mtime and previous is not None:
            os.utime(path, (previous + 2, previous + 2))

    def test_uses_config_path_environment_variable(self):
        self._write_config({"materials": {"custom": {"name": "FromEnv"}}})
        previous = os.environ.get('CONFIG_PATH')
        os.environ['CONFIG_PATH'] = self.config_path
        try:
            cfg = Config()
            self.assertEqual(cfg.config_file, self.config_path)
            self.assertEqual(cfg.get_materials()['custom']['name'], 'FromEnv')
        finally:
            if previous is None:
                os.environ.pop('CONFIG_PATH', None)
            else:
                os.environ['CONFIG_PATH'] = previous

    def test_defaults_to_config_json_when_env_unset(self):
        previous = os.environ.pop('CONFIG_PATH', None)
        try:
            cfg = Config()
            self.assertEqual(cfg.config_file, 'config.json')
        finally:
            if previous is not None:
                os.environ['CONFIG_PATH'] = previous

    def test_getters_reload_when_file_mtime_changes(self):
        self._write_config({
            "materials": {"pla": {"name": "Old PLA"}},
            "pricing": {"base_cost": 10, "pricing_mode": "custom"},
            "print_quality": {"draft": {"name": "Old Draft"}},
            "printers": {"prusa": {"name": "Old Printer", "enabled": True}},
            "post_processing": {"sanding": {"name": "Old Sand", "enabled": True}},
            "slicer": {"path": "/old/slicer"},
        })
        cfg = Config(self.config_path)

        self.assertEqual(cfg.get_materials()['pla']['name'], 'Old PLA')
        self.assertEqual(cfg.get_pricing_config()['base_cost'], 10)
        self.assertEqual(cfg.get_pricing_mode(), 'custom')
        self.assertEqual(cfg.get_print_qualities()['draft']['name'], 'Old Draft')
        self.assertEqual(cfg.get_printers()['prusa']['name'], 'Old Printer')
        self.assertEqual(cfg.get_enabled_printers()['prusa']['name'], 'Old Printer')
        self.assertEqual(cfg.get_post_processing_options()['sanding']['name'], 'Old Sand')
        self.assertEqual(cfg.get_slicer_path(), '/old/slicer')
        self.assertEqual(cfg.get('pricing', 'base_cost'), 10)
        self.assertEqual(cfg.config_data['materials']['pla']['name'], 'Old PLA')

        self._write_config({
            "materials": {"pla": {"name": "New PLA"}},
            "pricing": {"base_cost": 99, "pricing_mode": "per_gram"},
            "print_quality": {"draft": {"name": "New Draft"}},
            "printers": {"prusa": {"name": "New Printer", "enabled": True}},
            "post_processing": {"sanding": {"name": "New Sand", "enabled": True}},
            "slicer": {"path": "/new/slicer"},
        }, bump_mtime=True)

        self.assertEqual(cfg.get_materials()['pla']['name'], 'New PLA')
        self.assertEqual(cfg.get_material('pla')['name'], 'New PLA')
        self.assertEqual(cfg.get_pricing_config()['base_cost'], 99)
        self.assertEqual(cfg.get_pricing_mode(), 'per_gram')
        self.assertEqual(cfg.get_print_qualities()['draft']['name'], 'New Draft')
        self.assertEqual(cfg.get_printers()['prusa']['name'], 'New Printer')
        self.assertEqual(cfg.get_printer('prusa')['name'], 'New Printer')
        self.assertEqual(cfg.get_enabled_printers()['prusa']['name'], 'New Printer')
        self.assertEqual(cfg.get_post_processing_options()['sanding']['name'], 'New Sand')
        self.assertEqual(cfg.get_enabled_post_processing()['sanding']['name'], 'New Sand')
        self.assertEqual(cfg.get_post_processing('sanding')['name'], 'New Sand')
        self.assertEqual(cfg.get_slicer_path(), '/new/slicer')
        self.assertEqual(cfg.get('pricing', 'base_cost'), 99)
        self.assertEqual(cfg.config_data['materials']['pla']['name'], 'New PLA')

    def test_save_updates_mtime_and_keeps_in_memory_writes(self):
        self._write_config({"pricing": {"base_cost": 1}})
        cfg = Config(self.config_path)
        cfg.config_data = {"pricing": {"base_cost": 42}}
        self.assertTrue(cfg.save())
        self.assertEqual(cfg.get_pricing_config()['base_cost'], 42)

        other = Config(self.config_path)
        self.assertEqual(other.get_pricing_config()['base_cost'], 42)

    def test_save_writes_atomically_without_temp_leftovers(self):
        self._write_config({"pricing": {"base_cost": 1}})
        cfg = Config(self.config_path)
        cfg.config_data = {"pricing": {"base_cost": 7}, "materials": {"pla": {"name": "PLA"}}}
        self.assertTrue(cfg.save())

        leftovers = [
            name for name in os.listdir(self._tmpdir.name)
            if name.endswith('.tmp') or name.startswith('.config-')
        ]
        self.assertEqual(leftovers, [])
        with open(self.config_path) as handle:
            saved = json.load(handle)
        self.assertEqual(saved['pricing']['base_cost'], 7)


if __name__ == '__main__':
    unittest.main()
