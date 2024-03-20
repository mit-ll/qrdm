FROM python:3.11-bullseye as base
USER root

# Build injects image tag to enable self-referential docker-compose.yml so users
# can easily extract a runnable version of the docker-compose.yml from the container image.
ARG IMAGE_TAG

# Create and switch to restricted runtime-user account
RUN groupadd -g 1000 runtime-group \
	&& useradd --no-log-init \
	--uid 1000 \
	--gid 1000 \
	--expiredate -1 \
	--key PASS_MAX_DAYS=-1 \
	--key PASS_MIN_DAYS=-1 \
	runtime-user

# Install QR decoding library
RUN set -eux && \
	apt-get update && \
	apt-get install -y --no-install-recommends libzbar0 && \
	apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false && \
	rm -rf /var/lib/apt/lists/* && \
	apt clean

# Create runtime virtual environment
RUN mkdir -p /opt/venvs && python -m venv /opt/venvs/qrdm

ENV VIRTUAL_ENV=/opt/venvs/qrdm
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy and install package
RUN mkdir /app
COPY . /app
RUN sed -i 's/${IMAGE_TAG:-latest}/'"$IMAGE_TAG"'/g' /app/docker-compose.yml

WORKDIR /app
RUN python -m pip install --upgrade pip

FROM base as qrdm-ui

RUN python -m pip install --no-cache-dir .[frontend]

USER runtime-user

# By default setup env vars for running standalone with "localhost"
ENV STREAMLIT_SERVER_ADDRESS=localhost
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_BASE_URL_PATH=/
ENV STREAMLIT_SERVER_ENABLE_CORS=true
ENV STREAMLIT_BROWSER_SERVER_ADDRESS=localhost
ENV STREAMLIT_BROWSER_SERVER_PORT=8501

# Start up Web UI
EXPOSE ${STREAMLIT_SERVER_PORT}
ENTRYPOINT ["streamlit", "run", "ui/QRDM_Home.py", \
				"--browser.gatherUsageStats=false", \
				"--client.toolbarMode=viewer" \
			]

FROM base as qrdm-api

RUN python -m pip install --no-cache-dir .[backend]

USER runtime-user
WORKDIR /app

ENV QRDM_SERVER_PORT=8182
ENV QRDM_SERVER_ADDRESS=localhost
ENV QRDM_NUM_WORKERS=1
ENV QRDM_BASE_URL_PATH=/
ENV QRDM_JSON_LOGS=true
ENV QRDM_LOG_LEVEL=INFO

EXPOSE ${QRDM_SERVER_PORT}
ENTRYPOINT [ "bash", "-c", "exec uvicorn qrdm.backend:app --workers $QRDM_NUM_WORKERS --host $QRDM_SERVER_ADDRESS --port $QRDM_SERVER_PORT --root-path $QRDM_BASE_URL_PATH"  ]
