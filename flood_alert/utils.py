import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import smtplib
import ssl
import email
from dotenv import load_dotenv, find_dotenv
import os
import datetime as dt
from time import sleep
import matplotlib.pyplot as plt
import plotly.express as px
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
import seaborn as sns
import base64
from io import BytesIO, StringIO
import tempfile
from email import encoders
from os.path import basename


def table_and_level(base_url, params, checkpoints):
    """
    returns the biggest visible table on a given url destination, the alert level of the tides for several
    checkpoints and the list of notification levels for each checkpoint in a dictionary:
                                  {<checkpoint>:{'df':<df>,
                                                'alert_lvl':<lvl>,
                                                'level_list':<[list]>
                                                }
                                  }.
    takes in base_url (term '___placeholder___' is in the string to insert checkpoint id),
    params (to feed the get request)
    and a dictionary of the checkpoint_id (string) as keys and a list of threshold notification levels as values.
    """
    print('table_and_level() was called.')
    results = {}
    for checkpoint, level_list in checkpoints.items():
        print(f'handling {checkpoint}.')
        url = base_url.replace('___placeholder___', checkpoint)
        r = requests.get(url, params=params)

        # get all tables
        tables = pd.read_html(r.content)

        # find the biggest table on page
        lens = [len(x) for x in tables]
        max_ = lens.index(max(lens))

        # get table and prepare
        df = tables[max_]
        df.columns = ['Datum', f'Wasserstand_{checkpoint}']
        df['Datum'] = pd.to_datetime(df.Datum, format='%d.%m.%Y %H:%M')
        df_recent_lvl = df.loc[0, f'Wasserstand_{checkpoint}']

        # check which level is reached
        alert_check = [df_recent_lvl > lvl for lvl in level_list]

        results[checkpoint] = {'df':df,
                        'alert_lvl':sum(alert_check),
                        'level_list':level_list}
    return results

def plot_recent_html(df, lvls):
    """
    Returns the water level plot html encoded filtered to the last 12 hours.
    """
    # filter df
    df_recent = df.head(48)

    # set plot
    fig = plt.figure()
    plt.ion() # don't show plot
    sns.lineplot(data=df_recent.set_index('Datum'))
    plt.xticks(rotation=45)
    # plot lvls
    for i,lvl in enumerate(lvls):
        sns.lineplot(x=df_recent.Datum, y=lvl, label=f'Stufe {i+1}')
    plt.legend()
    plt.grid(axis='y')
    plt.xlabel('Uhrzeit')
    plt.ylabel('Wasserstand (cm) ueber NN')
    plt.title('Development last 12 hours', size=12)
    plt.tight_layout()

    plt.close(fig)

    # save plot
    tmpfile = BytesIO()
    fig.savefig(tmpfile, format='png')
    encoded = base64.b64encode(tmpfile.getvalue()).decode('utf-8')
    plot_html = '<br><br>' + '<img src=\'data:image/png;base64,{}\'>'.format(encoded) + "<br><br>"

    return plot_html

def send_email(homename, sender_email, receiver_email, password, port, signature, lvl_results, debug):
    """
    Compiles an Email with the email.mime library and sends it through a Google Mail smtp server.
    Takes in variables for the mail content [homename (str), lvl_results (dict), signature (str)]
    and settings to send the email [sender_email, receiver_email, password, port]
    There is a debug argument to test the email function despite a trigger isn't reached.
    """
    print('send email was called.')
    # check, if there is any alert in the checkpoints
    if any([x.get('alert_lvl') for x in lvl_results.values()]) or debug:
        print('there is an alert!')
        # compile email msg
        now = dt.datetime.now().strftime("%y-%m-%d %H:%M:%S")
        msg = MIMEMultipart('mixed')
        msg['Subject'] = f"{homename} -WATER ALERT- {now}"
        msg['From'] = f'{homename} <{sender_email}>'
        msg['To'] = ','.join(receiver_email)

        # init msg
        init = "<p>***ALERT***, <br>Es wurde ein ueberhoehter Wasserstand gemeldet.<br><br></p>"
        # get contents
        today = dt.datetime.today().date()

        # unpack dfs
        plots_html = [plot_recent_html(vals.get('df'), vals.get('level_list')) for id_, vals in lvl_results.items()]
        alert_levels_html = [f"<p>Alert level {key}: {val.get('alert_lvl')}</p>" for key, val in lvl_results.items()]

        # merge all html per checkpoint together
        together = '<br><br>'.join([f'{alert_levels_html[x]}\
                                        <br><br>{plots_html[x]}' for x in range(len(plots_html))])

        # Record the MIME types of text/html.
        text = MIMEMultipart('alternative')
        text.attach(MIMEText(init + together + signature, 'html', _charset="utf-8"))

        # add all parts to msg
        msg.attach(text)

        # create tables as .csv from temp files
        tempdir = tempfile.gettempdir()
        filenames = [f'{tempdir}/{name}.csv' for name in lvl_results.keys()]
        # filter and save csv tables
        save_files = [value.get('df').head(48).to_csv(f'{tempdir}/{key}.csv') for key, value in lvl_results.items()]
        for file_ in filenames:
            with open(file_, "rb") as fil:
                part = MIMEApplication(
                        fil.read(),
                        Name=basename(file_))

            part['Content-Disposition'] = f'attachment; filename={basename(file_)}'
            msg.attach(part)

        # Create a secure SSL context
        context = ssl.create_default_context()

        with smtplib.SMTP_SSL("smtp.gmail.com", port, context=context) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, msg.as_string())

        print(f'successfully sent emails to {receiver_email}')
    else:
        _ = [print(f'There was no alert at {id_}') for id_ in lvl_results.keys()]
        print('Exit function without sending mail.')
