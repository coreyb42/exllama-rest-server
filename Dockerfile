FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04 as build
ARG RUN_UID="1000"
ARG APPLICATION_STATE_PATH="/data"
ENV RUN_UID=$RUN_UID \
    APPLICATION_STATE_PATH=$APPLICATION_STATE_PATH \
    CONTAINER_MODEL_PATH=$APPLICATION_STATE_PATH/model \
    CONTAINER_SESSIONS_PATH=$APPLICATION_STATE_PATH/exllama_sessions

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y ninja-build python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Setup user which will run the service and create application state directory
RUN if [ ${RUN_UID} -ne 0 ] ; then useradd -m -u $RUN_UID user ; fi \
    && mkdir -p $APPLICATION_STATE_PATH \
    && mkdir -p $CONTAINER_MODEL_PATH \
    && mkdir -p $CONTAINER_SESSIONS_PATH \
    && chown -R $RUN_UID $APPLICATION_STATE_PATH
USER $RUN_UID


COPY --chown=$RUN_UID requirements.txt /app/
COPY --chown=$RUN_UID requirements-web.txt /app/

WORKDIR /app

RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && pip install -r requirements-web.txt

USER root
STOPSIGNAL SIGINT

COPY --chown=$RUN_UID . /app

ENTRYPOINT ["/bin/bash", "-c", "/app/entrypoint.sh $0 $@"]
