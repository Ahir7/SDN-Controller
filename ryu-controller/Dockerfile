FROM osrg/ryu:latest

# Install dependencies as root, then drop back to ryu user
USER root
RUN pip install --no-cache-dir kazoo kubernetes psycopg2-binary sqlalchemy

USER ryu
WORKDIR /app
COPY . .

# The CMD will be to run our custom Ryu app
CMD ["ryu-manager", "zt_controller.py"]