from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter

from opentelemetry import trace
from prometheus_client import Counter, Histogram, start_http_server


# Prometheus raccoglie questi contatori e l'istogramma per la dashboard Grafana.
RICHIESTE = Counter("manuali_richieste", "Richieste per esito", ["esito"])
LATENZA = Histogram("manuali_latenza_secondi", "Latenza end-to-end")
STRUMENTI = Counter("manuali_tool", "Chiamate agli strumenti", ["tool"])
_RICHIESTA_ATTIVA: ContextVar[dict[str, str] | None] = ContextVar("richiesta_attiva", default=None)


def avvia_osservabilita(porta: int, endpoint: str):
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    start_http_server(porta)
    provider = TracerProvider(resource=Resource.create({
        "service.name": "manuali-auto", "openinference.project.name": "manuali-auto",
    }))
    # Le tracce delle singole richieste vanno a Phoenix tramite OTLP su HTTP.
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    return provider


@contextmanager
def span(nome: str, tipo: str, **attributi):
    attributi["openinference.span.kind"] = tipo
    with trace.get_tracer("manuali-auto").start_as_current_span(nome, attributes=attributi) as corrente:
        yield corrente


@contextmanager
def richiesta():
    # La chat e l'agente possono condividere lo stesso conteggio per un singolo turno.
    attiva = _RICHIESTA_ATTIVA.get()
    if attiva is not None:
        yield attiva
        return

    inizio = perf_counter()
    with span("richiesta", "CHAIN") as corrente:
        esito = {"valore": "errore"}
        token = _RICHIESTA_ATTIVA.set(esito)
        try:
            yield esito
        finally:
            _RICHIESTA_ATTIVA.reset(token)
            # La richiesta viene misurata anche se un errore impedisce di impostare un altro esito.
            corrente.set_attribute("esito", esito["valore"])
            RICHIESTE.labels(esito["valore"]).inc()
            LATENZA.observe(perf_counter() - inizio)


@contextmanager
def strumento(nome: str):
    STRUMENTI.labels(nome).inc()
    with span(nome, "TOOL") as corrente:
        yield corrente
