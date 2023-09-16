FROM python:3.11

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev python3-setuptools \
    fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 \
    libnspr4 libnss3 lsb-release xdg-utils libxss1 libdbus-glib-1-2 \
    curl unzip wget xvfb

ENV GECKODRIVER_VERSION v0.33.0
RUN wget https://github.com/mozilla/geckodriver/releases/download/$GECKODRIVER_VERSION/geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz && \
    tar -zxf geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz -C /usr/local/bin && \
    chmod +x /usr/local/bin/geckodriver && \
    ls -l . && \
    rm geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz

RUN FIREFOX_SETUP=firefox-setup.tar.bz2 && \
    apt-get purge firefox && \
    wget -O $FIREFOX_SETUP "https://download.mozilla.org/?product=firefox-latest&os=linux64" && \
    tar xjf $FIREFOX_SETUP -C /opt/ && \
    ln -s /opt/firefox/firefox /usr/bin/firefox && \
    rm $FIREFOX_SETUP

RUN pip3 install selenium pyvirtualdisplay Selenium-Screenshot fastapi uvicorn telegraph[aio] html-telegraph-poster

COPY . /app

WORKDIR /app

CMD ["uvicorn", "reader_web_service:app", "--host", "0.0.0.0", "--port", "8095"]
