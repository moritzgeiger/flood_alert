import requests
from bs4 import BeautifulSoup
import pandas as pd
import smtplib
import ssl
import datetime as dt
from time import sleep
import matplotlib.pyplot as plt
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import seaborn as sns
import base64
from io import BytesIO


def pd_table(base_url, params, alert_levels):
    """
    returns the biggest visible table on a given url destination.
    takes in base_url and params (using requests)
    """
    print('pd_table was called.')
    print(f'fetching table from {base_url}')
    r = requests.get(base_url, params=params)

    # get all tables
    tables = pd.read_html(r.content)

    # find the biggest table on page
    lens = [len(x) for x in tables]
    max_ = lens.index(max(lens))

    # get table and prepare
    df = tables[max_]
    df.columns = ['Datum', 'Wasserstand']
    df['Datum'] = pd.to_datetime(df.Datum, format='%d.%m.%Y %H:%M')

    for k, v in alert_levels.items():
        df[k] = df.Wasserstand - v

    return df

def alert(df):
    """
    Returns the alert level of the reported last timestamp.
    """
    print('alert was called.')
    return (df.set_index('Datum').head(1) > 0).values.sum() - 1

def plot_today_html(df, alert_levels):
    """
    Returns the water level plot html encoded filtered to today.
    """
    print('plot_today_html was called.')
    # filter df
    today = dt.datetime.today().date()
    df_today = df[df.Datum.dt.date == today]

    # set plot
    fig = plt.figure()
    plt.ion() # don't show plot
    sns.lineplot(data=df_today.set_index('Datum').Wasserstand,
                 label='Wasserstand')
    for k,v in alert_levels.items():
        sns.lineplot(x=df_today.Datum, y=v, label=k)
    plt.xticks(rotation=90)
    plt.legend()
    plt.grid(axis='y')
    plt.close(fig)

    # save plot
    tmpfile = BytesIO()
    fig.savefig(tmpfile, format='png')
    encoded = base64.b64encode(tmpfile.getvalue()).decode('utf-8')
    plot_html = 'Development today:<br><br>' \
      + '<img src=\'data:image/png;base64,{}\'>'.format(encoded) \
        + "<br><br>"

    return plot_html

def compile_email(homename, sender_email, receiver_email, signature, df, alert_levels):
    """
    Compiles email with MIMEMultipart to make it sendable through smtplib (html).
    Takes these arguments: homename, sender_email, receiver_email, signature, df, alert_levels
    """
    print('compilr_email was called.')
    now = dt.datetime.now().strftime("%y-%m-%d %H:%M:%S")
    # compile email msg
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"{homename} stats at {now}"
    msg['From'] = f'Muehlennews <{sender_email}>'
    msg['To'] = receiver_email

    # init msg
    init = "<p>Hi, <br><br>Here are the new water level stats from today.<br><br></p>"

    # get contents
    today = dt.datetime.today().date()
    table_html = df[df.Datum.dt.date == today].to_html()
    plot_html = plot_today_html(df, alert_levels)
    alert_level_html = f"<p>Alert level: {alert(df)}</p>"

    # Record the MIME types of both parts - text/plain and text/html.
    part1 = MIMEText(init + alert_level_html + plot_html + table_html + signature, 'html')

    # Attach parts into message container.
    msg.attach(part1)

    return msg


def send_mail(port,
            password,
            receiver_email,
            message,
            sender_email):
    """
    takes in arguments neccessary to send an email.
    args: port, password, receiver_email, message, sender_email

    initiates sending of an email.
    """
    print('send_mail was called.')
    # Create a secure SSL context
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL("smtp.gmail.com", port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message)

    print(f'mail was sent to {receiver_email}')
