"""Stress tests verifying dynamic tracing on decorator-heavy CLI frameworks like click."""

import click
from click.testing import CliRunner
from umldoc.extractors.dynamic_trace import ExecutionTracer
from umldoc.ir.dynamic_model import InteractionEventType


def test_click_command_hierarchy_tracing():
    """Trace click command execution, option parsing, and subcommand dispatch."""
    @click.group()
    def cli():
        """Top-level CLI group."""
        pass

    @cli.command("deploy")
    @click.option("--env", default="staging", help="Target environment")
    @click.argument("service_name")
    def deploy_command(env: str, service_name: str):
        click.echo(f"Deploying {service_name} to {env}")

    runner = CliRunner()

    tracer = ExecutionTracer(
        scenario_name="Click_Deploy_CLI",
        entrypoint_name="runner.invoke",
        include_prefixes={"click", "tests"},
    )

    with tracer:
        result = runner.invoke(cli, ["deploy", "auth-service", "--env", "production"])

    assert result.exit_code == 0
    assert "Deploying auth-service to production" in result.output

    session = tracer.get_session_ir()
    assert session.scenario_name == "Click_Deploy_CLI"
    assert len(session.participants) >= 2
    assert len(session.interactions) >= 4

    call_events = [e for e in session.interactions if e.event_type == InteractionEventType.CALL]
    method_names = [e.method_name for e in call_events]

    # Verify key click lifecycle methods were cleanly captured
    assert any("invoke" in m or "deploy_command" in m for m in method_names)
