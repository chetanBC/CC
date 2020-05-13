FROM python:3.7-slim-stretch

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

ADD . /todo
WORKDIR /todo
RUN pip install -r requirements.txt
CMD [ "rides.py" ]
ENV TEAM_NAME "CC_1375_1419_1703_1878"