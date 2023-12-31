#!/usr/local/bin/python
"""Module defining the entrypoint to the Prometheus exporter."""
import click
import json
import prometheus_client
import prometheus_client.core
import prometheus_client.metrics_core
import prometheus_client.registry
import time


class FactorioCollector(prometheus_client.registry.Collector):
    metrics_path: str = ""

    def __init__(self, metrics_path: str) -> None:
        self.metrics_path = metrics_path

    def collect(self) -> None:
        with open(file=self.metrics_path, mode="r", encoding="utf-8") as f:
            data = json.load(f)

        # Collect the current game tick.
        yield prometheus_client.metrics_core.GaugeMetricFamily(
            "factorio_game_tick",
            "The current tick of the running Factorio game.",
            value=data["game"]["time"]["tick"],
        )

        # Collect the player states.
        player_connection_states = prometheus_client.metrics_core.GaugeMetricFamily(
            "factorio_player_connected",
            "The current connection state of the player.",
            labels=["username"],
        )
        for username, state in data["players"].items():
            player_connection_states.add_metric(
                labels=[username],
                value=int(state["connected"]),
            )
        yield player_connection_states

        # Collect the force statistics.
        force_consumption_stats = prometheus_client.metrics_core.CounterMetricFamily(
            name="factorio_force_prototype_consumption",
            documentation="The total consumption of a given prototype for a force.",
            labels=["force", "prototype", "type"],
        )
        force_production_stats = prometheus_client.metrics_core.CounterMetricFamily(
            name="factorio_force_prototype_production",
            documentation="The total production of a given prototype for a force.",
            labels=["force", "prototype", "type"],
        )
        force_research_progress = prometheus_client.metrics_core.GaugeMetricFamily(
            name="factorio_force_research_progress",
            documentation="The current research progress percentage (0-1) for a force.",
            labels=["force"],
        )
        for force_name, force_data in data["forces"].items():
            for type_name, prototypes in force_data.items():
                if type_name == "research":
                    force_research_progress.add_metric(
                        labels=[force_name],
                        value=force_data["research"]["progress"],
                    )

                if type_name in {"fluids", "items"}:
                    for prototype_name, production in prototypes.items():
                        force_consumption_stats.add_metric(
                            labels=[force_name, prototype_name, type_name],
                            value=production["consumption"],
                        )
                        force_production_stats.add_metric(
                            labels=[force_name, prototype_name, type_name],
                            value=production["production"],
                        )
        yield force_consumption_stats
        yield force_production_stats
        yield force_research_progress

        # Collect the pollution statistics.
        pollution_stats = prometheus_client.metrics_core.GaugeMetricFamily(
            name="factorio_pollution_production",
            documentation="The pollution produced or consumed from various sources.",
            labels=["source"],
        )
        for source, pollution in data["pollution"].items():
            pollution_stats.add_metric(labels=[source], value=pollution)
        yield pollution_stats


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option(
    "--metrics-path",
    default="/factorio/script-output/metrics.json",
    help="Path to watch.",
)
@click.option(
    "--metrics-port",
    type=click.INT,
    default=9102,
    help="TODO",
)
def run(metrics_path: str, metrics_port: int) -> None:
    # Unregister the default collectors.
    prometheus_client.core.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)
    prometheus_client.core.REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)
    prometheus_client.core.REGISTRY.unregister(prometheus_client.PROCESS_COLLECTOR)

    # Register the Factorio collector.
    prometheus_client.core.REGISTRY.register(
        FactorioCollector(metrics_path=metrics_path),
    )

    # Start the Prometheus server in a thread.
    prometheus_client.start_http_server(metrics_port)

    # Keep looping until we receive an interruption.
    try:
        while True:
            time.sleep(1)
    finally:
        pass


if __name__ == "__main__":
    cli()
