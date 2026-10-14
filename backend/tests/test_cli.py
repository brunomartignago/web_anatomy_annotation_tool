from typer.testing import CliRunner

from annotool import __version__
from annotool.cli import app

runner = CliRunner()


def test_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"annotool {__version__}"


def test_help_flag_shows_usage():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.stdout
