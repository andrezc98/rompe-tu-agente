"""Test-harness infrastructure only; no test logic lives here.

Isolate boto3/botocore from this machine's real ~/.aws files, and give the
fake "test-sandbox" profile used in tests/test_tools.py a profile section
to resolve against.

botocore resolves lookups like ca_bundle, region and the data loader's
data_path through get_scoped_config(), which reads AWS_PROFILE fresh (no
caching) and raises ProfileNotFound whenever that profile is not a defined
config section. This happens for any boto3.client() call, even one passing
explicit fake credentials, and even with no ~/.aws files at all (verified
by pointing HOME at an empty directory). tests/test_tools.py sets
AWS_PROFILE to "test-sandbox", a profile that exists nowhere, so without
this fixture every stubbed client creation raises ProfileNotFound before
the test body runs -- and it also means test runs can never fall through
to this machine's real AWS config or credentials.
"""

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolated_aws_files(tmp_path_factory):
    config_dir = tmp_path_factory.mktemp("aws-config")
    (config_dir / "config").write_text("[profile test-sandbox]\n")
    (config_dir / "credentials").write_text("")

    mp = pytest.MonkeyPatch()
    mp.setenv("AWS_CONFIG_FILE", str(config_dir / "config"))
    mp.setenv("AWS_SHARED_CREDENTIALS_FILE", str(config_dir / "credentials"))
    yield
    mp.undo()
