heatmap:
	docker run \
		-e OUTPUT_PATH=/heatmap/heatmap.gpkg \
		-e COLLIDEOSCOPE_DATABASE_URL \
		-v ${PWD}:/heatmap \
		-t davea/collideoscope-heatmap

build:
	docker build -t davea/collideoscope-heatmap .
