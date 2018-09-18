FROM kennethreitz/pipenv

RUN apt-get update && apt-get install -y libsqlite3-mod-spatialite \
    && rm -rf /var/lib/apt/lists/*

COPY generate_heatmap.py /app

CMD python3 generate_heatmap.py
