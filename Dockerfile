FROM python:3.12.2-bullseye

RUN apt-get update
RUN apt-get install firefox-esr -y

WORKDIR /usr/src/app
ENV DB_FILE=ilpostcast.db

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN ./get_geckodriver.sh
CMD [ "python", "./ilpostcast/scrape.py" ]
