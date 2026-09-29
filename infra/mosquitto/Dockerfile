FROM eclipse-mosquitto:2.0.22
COPY mosquitto.conf acl.template /mosquitto/config/
COPY entrypoint.sh /usr/local/bin/aivms-entrypoint.sh
RUN chmod +x /usr/local/bin/aivms-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/aivms-entrypoint.sh"]
