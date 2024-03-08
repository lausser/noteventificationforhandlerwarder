# podman build -t python-project .
# podman run -it --rm --security-opt label=disable -v "$(pwd)":/app python-project
FROM python:3.8-slim
WORKDIR /app-prep
RUN python -m pip install --upgrade pip
COPY . /app-prep
RUN python -m pip install .
RUN python -m pip install .[test]
WORKDIR /app
ENTRYPOINT ["/bin/bash", "-i"]

