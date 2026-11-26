# SPDX-License-Identifier: GPL-3.0-or-later
"""The sweep never restarts a VM that is wanted stopped (owner, 2026-11-22).

tools/jobs/sweep.sh must leave the VM to tools/gcp/gcp.py sweep (no gcloud call of its own), and gcp.py's sweep must
start a stopped VM only while wanted.json says "running"."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'gcp'))
import gcp  # noqa: E402

SWEEP = HERE / 'sweep.sh'


class SweepScript(unittest.TestCase):
    def test_no_vm_control_of_its_own(self):
        text = SWEEP.read_text(encoding='utf-8')
        code = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))
        self.assertNotIn('gcloud', code)
        self.assertNotIn('instances start', code)

    def test_vm_goes_through_gcp_sweep(self):
        self.assertIn('tools/gcp/gcp.py" sweep', SWEEP.read_text(encoding='utf-8'))

    def test_pagefile_logged(self):
        """The pagefile sits on C: and once grew into its reserve: logged with C: free every run."""
        self.assertIn('Win32_PageFileUsage', SWEEP.read_text(encoding='utf-8'))

    def test_no_token_or_paged_pool_checks(self):
        """Owner, 2026-11-24: the token leak gets no restart rule; the token and paged-pool checks are gone."""
        text = SWEEP.read_text(encoding='utf-8')
        for gone in ('PAGED_POOL_ALERT_GB', 'PoolPagedBytes', 'pool_tags.ps1', 'Toke'):
            self.assertNotIn(gone, text)
        self.assertFalse((HERE / 'pool_tags.ps1').exists())

    def test_wsl_disk_sizes_logged(self):
        """Owner, 2026-11-24: track C: and the Ubuntu vhdx size in the sweep; the distros come from the registry."""
        text = SWEEP.read_text(encoding='utf-8')
        self.assertIn('tools/jobs/wsl_disks.ps1"', text)
        ps1 = (HERE / 'wsl_disks.ps1').read_text(encoding='utf-8')
        self.assertIn('CurrentVersion\\Lxss', ps1)
        self.assertNotRegex(ps1, r'(?i)c:\\users\\[a-z0-9]')   # no user path written in


class GcpSweepWanted(unittest.TestCase):
    def run_sweep(self, wanted, status='TERMINATED'):
        with tempfile.TemporaryDirectory() as tmp:
            sd = Path(tmp)
            (sd / 'wanted.json').write_text(json.dumps({'wanted': wanted}), encoding='utf-8')
            calls = []

            def fake_gcloud(c, *args, **kw):
                calls.append(args)
                return mock.Mock(returncode=0, stdout='', stderr='')

            vm = {'status': status, 'ip': None, 'machine_type': 'test'}
            with mock.patch.object(gcp, 'state_dir', return_value=sd), \
                    mock.patch.object(gcp, 'describe', return_value=vm), \
                    mock.patch.object(gcp, 'preemptions', return_value=[]), \
                    mock.patch.object(gcp, 'gcloud', side_effect=fake_gcloud), \
                    mock.patch.object(gcp, 'alert'), \
                    mock.patch('builtins.print'):
                gcp.cmd_sweep({'instance': 'vm', 'zone': 'z'})
            return [a for a in calls if 'start' in a]

    def test_wanted_stopped_is_never_started(self):
        for status in ('TERMINATED', 'STOPPED', 'SUSPENDED'):
            self.assertEqual(self.run_sweep('stopped', status), [], status)

    def test_no_wanted_state_is_never_started(self):
        self.assertEqual(self.run_sweep(None), [])

    def test_preempted_while_wanted_running_is_started(self):
        self.assertEqual(len(self.run_sweep('running')), 1)


if __name__ == '__main__':
    unittest.main()
