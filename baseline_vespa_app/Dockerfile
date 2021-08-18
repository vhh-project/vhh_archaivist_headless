FROM vespaengine/vespa

COPY launch-vespa.sh .
COPY wait-for-config-server.sh .
RUN chmod +x /launch-vespa.sh /wait-for-config-server.sh
ENTRYPOINT ["/launch-vespa.sh"]