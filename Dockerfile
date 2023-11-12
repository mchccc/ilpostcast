FROM python:3.12-bullseye

RUN apt-get update && apt-get install chromium chromium-driver rustc -y

WORKDIR /usr/src/app
ENV DB_FILE=ilpostcast.db

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD [ "python", "./ilpostcast/scrape.py" ]
