import redis
from flask import Flask
import os

from flask import Flask
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.cloud_trace_propagator import (
    CloudTraceFormatPropagator,
)

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Link

set_global_textmap(CloudTraceFormatPropagator())

tracer_provider = TracerProvider()
cloud_trace_exporter = CloudTraceSpanExporter()
tracer_provider.add_span_processor(
    # BatchSpanProcessor buffers spans and sends them in batches in a
    # background thread. The default parameters are sensible, but can be
    # tweaked to optimize your performance
    BatchSpanProcessor(cloud_trace_exporter)
)
trace.set_tracer_provider(tracer_provider)

tracer = trace.get_tracer(__name__)


app = Flask(__name__)

from google.cloud import secretmanager

client = secretmanager.SecretManagerServiceClient()
#name = f"projects/966837857153/secrets/redis-pass/versions/2"
name = os.environ.get("AUTHSTR", "<default value>")

readipvar = os.environ.get("READIP", '<default value>' )
writeipvar = os.environ.get("WRITEIP", '<default value>' )
passwordsec = client.access_secret_version(name=name)
passwordvar = passwordsec.payload.data.decode("UTF-8")
print(passwordvar)
print(name)

import sys

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
certCA = open("server-ca.pem","r")


@app.route("/write")
def hello_world():
    
    with tracer.start_span("write-connection") as current_span:
      r = redis.Redis(host=writeipvar, port='6379', db='0', password=passwordvar)
    
    with tracer.start_as_current_span("write") as current_span:
      r.set('foo','bar')
      r.expire('foo',20)

    return "done!"

@app.route("/read")
def read():

    with tracer.start_span("read-connection") as current_span:
      r1 = redis.Redis(host=readipvar, port='6379', db='0', password=passwordvar)
      
    with tracer.start_as_current_span("read-test") as current_span:
      if(r1.get('foo')):
        with tracer.start_as_current_span("read-test-redis") as current_span:
          val1 = r1.get('foo')
      else:
        with tracer.start_as_current_span("read-test-redis-write") as current_span:
          r1 = redis.Redis(host=writeipvar, port='6379', db='0', password=passwordvar)
          r1.set('foo','bar')
          r1.expire('foo',20)
          val1 = r1.get('foo')
    return val1

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
