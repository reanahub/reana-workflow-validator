# This file is part of REANA.
# Copyright (C) 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

# Use alpine base image
FROM docker.io/library/python:3.12-alpine

RUN pip install --upgrade pip

RUN adduser -D worker
USER worker
WORKDIR /home/worker

COPY --chown=worker:worker requirements.txt requirements.txt
RUN pip install --user -r requirements.txt

COPY --chown=worker:worker ./reana-workflow-validator .

CMD ["python", "main.py"]

# Set image labels
LABEL org.opencontainers.image.authors="team@reanahub.io"
LABEL org.opencontainers.image.created="2024-03-04"
LABEL org.opencontainers.image.description="REANA reproducible analysis platform - workflow validator component"
LABEL org.opencontainers.image.documentation="https://reana-workflow-validator.readthedocs.io/"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/reanahub/reana-workflow-validator"
LABEL org.opencontainers.image.title="reana-workflow-validator"
LABEL org.opencontainers.image.url="https://github.com/reanahub/reana-workflow-validator"
LABEL org.opencontainers.image.vendor="reanahub"
# x-release-please-start-version
LABEL org.opencontainers.image.version="0.95.0-alpha.1"
# x-release-please-end
