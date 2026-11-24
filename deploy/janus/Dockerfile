FROM python:3.12-slim
WORKDIR /app
COPY sentinel.py janus.py ./
ENV NOCTUA_DB=/data/noctua.db NOCTUA_USERS=/config/users.json \
    NOCTUA_CASES=/config/cases.json NOCTUA_PORT=8080
EXPOSE 8080
CMD ["python3", "janus.py"]
