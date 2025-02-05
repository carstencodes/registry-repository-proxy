FROM python:3.11-alpine3.15

EXPOSE 8000

ENV PROXY_CONFIG_FILE=/etc/proxy/proxy.json

RUN pip install falcon gunicorn \
   && mkdir -p /usr/lib/falcon/proxy \
   && addgroup -S falcon \
   && adduser -h /usr/lib/falcon/proxy -s /bin/sh -G falcon -S falcon \
   && chown -R falcon:falcon /usr/lib/falcon/proxy

COPY --chown=falcon:falcon proxy.py /usr/lib/falcon/proxy

WORKDIR /usr/lib/falcon/proxy

USER falcon:falcon

ENTRYPOINT [ "/usr/local/bin/gunicorn", "-b", "0.0.0.0", "proxy:app" ]
