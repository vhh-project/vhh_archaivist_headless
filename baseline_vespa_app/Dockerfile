FROM vespaengine/vespa:7.546.44

WORKDIR /baseline
COPY . .
RUN chmod +x launch-vespa.sh wait-for-config-server.sh
ENTRYPOINT ["/baseline/launch-vespa.sh"]
