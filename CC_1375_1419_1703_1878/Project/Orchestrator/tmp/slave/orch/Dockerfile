FROM python:3.7-slim-stretch

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

RUN mkdir -p /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install -r /code/requirements.txt

COPY . /code
WORKDIR /code

CMD ["python","orch.py"]

ENV TEAM_NAME "CC_1375_1419_1703_1878"

