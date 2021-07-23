import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import smtplib
import ssl
import datetime as dt
import matplotlib.pyplot as plt
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
import re
from google.cloud import storage


def table_and_level(base_url, params, checkpoints):
    """
    returns the biggest visible table on a given url destination, the alert level of the tides for several
    checkpoints and the list of notification levels for each checkpoint in a dictionary:
                                  {<checkpoint>:{'df':<df>,
                                                'alert_lvl':<lvl>,
                                                'level_list':<[list]>,
                                                'name':<normalized name>
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
        real_name = re.sub('[^A-Za-z]+', '', checkpoint).capitalize()
        df.columns = ['Datum', f'Wasserstand_{real_name}']
        df['Datum'] = pd.to_datetime(df.Datum, format='%d.%m.%Y %H:%M')
        df_recent_lvl = df.loc[0, f'Wasserstand_{real_name}']

        # check which level is reached
        alert_check = [df_recent_lvl > lvl for lvl in level_list]
        results[checkpoint] = {'df':df,
                               'name':real_name,
                              'alert_lvl':sum(alert_check),
                              'level_list':level_list}
    return results

def upload_file_gcp(source_file_bytes, file_name_uploaded, content_type, bucket_name=None):
    """Uploads a bytes pdf file to the bucket and returns the cloud link."""
    print("upload_file_gcp was called.")

    # Building connection with gcs
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    # opening a blob/destination name
    blob = bucket.blob(file_name_uploaded)

    # init upload => timeout needs to be high for big files
    blob.upload_from_string(source_file_bytes.getvalue(),
                            content_type=content_type,
                            timeout = 500.0,
                            )

    print(f"file uploaded as {blob.public_url}.")
    return blob.public_url

def upload_csv(lvl_results, bucket_name):
  """
  returns the url from an uploaded csv file to gcp.
  takes in a dictionary with at least one key ('df') and
  the bucket name of the gcp storage bucket.
  """
    # TODO: Save attachments to cloud to be attached
    # create tables as .csv from temp files
    # tempdir = tempfile.gettempdir()
    # filenames = [f'{tempdir}/{name}.csv' for name in lvl_results.keys()]
    # # filter and save csv tables
    # save_files = [value.get('df').head(48).to_csv(f'{tempdir}/{key}.csv') for key, value in lvl_results.items()]
    # for file_ in filenames:
    #     with open(file_, "rb") as fil:
    #         return upload_file_gcp(fil,
    #                         file_,
    #                         bucket_name=bucket_name,
    #                         content_type=?????)

def plot_recent_html(df, lvls, bucket_name=None):
    """
    Returns the water level plot html encoded filtered to the last 12 hours.
    """
    print('plot_html was called')
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
    plt.title('Entwicklung ueber die letzten 12 Stunden.', size=12)
    plt.tight_layout()

    plt.close(fig)

    if bucket_name:
        print(f'uploading to {bucket_name}')
        tmpfile = BytesIO()
        fig.savefig(tmpfile, format='png')
        now = dt.datetime.now().strftime('%Y%m%d%H%M%s%ms')
        print(now)
        # upload to cloud and get url
        file_url = upload_file_gcp(source_file_bytes=tmpfile,
                                   file_name_uploaded=f'recent_dev_{now}.png',
                                   bucket_name=bucket_name,
                                   content_type='image/png')
        html_img =  f'<img src="{file_url}" alt="Wasserstandsentwicklung 12 Stunden">'
        tmpfile.close()
        return html_img

    # save plot as html locally as temp
    else:
        tmpfile = BytesIO()
        fig.savefig(tmpfile, format='png')
        encoded = base64.b64encode(tmpfile.getvalue()).decode('utf-8')
        plot_html = '<br><br>' + '<img src=\'data:image/png;base64,{}\'>'.format(encoded) + "<br><br>"
        return plot_html


##### old send mail with mime
##### find new source for sendinblue skd in send_mail.py
def send_email(homename, sender_email, receiver_email, password, port, signature, lvl_results, debug):
    """
    Compiles an Email with the email.mime library and sends it through a Google Mail smtp server.
    Takes in variables for the mail content [homename (str), lvl_results (dict), signature (str)]
    and settings to send the email [sender_email, receiver_email, password, port]
    There is a debug argument to test the email function despite a trigger isn't reached.
    """
    print('send email was called.')
    # check, if there is alert level 2 was reached in the checkpoints
    if any([x.get('alert_lvl') > 1 for x in lvl_results.values()]) or debug:
        print('there is an alert!')
        # init msg
        init = "<p>***WASSERSTANDSALARM***, <br><br>Es wurde ein ueberhoehter Wasserstand gemeldet.<br><br></p>"

        # unpack dfs
        plots_html = [plot_recent_html(vals.get('df'), vals.get('level_list')) for id_, vals in lvl_results.items()]
        alert_levels_html = [f"<p><b>{i+1}. Meldestufe fuer {val.get('name').capitalize()}: {val.get('alert_lvl')}</b></p>" \
                              for i, (key, val) in enumerate(lvl_results.items())]

        # merge all html per checkpoint together
        together = '<br><br>'.join([f'{alert_levels_html[x]}\
                                        <br>{plots_html[x]}' for x in range(len(plots_html))])

        # Record the MIME types of text/html.
        text = MIMEMultipart('alternative')
        text.attach(MIMEText(init + together + signature, 'html', _charset="utf-8"))

        # find the highest level
        all_lvls = {x.get('name'):x.get('alert_lvl') for x in lvl_results.values()}
        town = max(all_lvls, key=all_lvls.get)

        # compile email msg
        now = dt.datetime.now().strftime("%y-%m-%d %H:%M")
        msg = MIMEMultipart('mixed')
        # avoid automized email ruling by subject when testing
        if debug:
            msg['Subject'] = f"-TESTALARM- Meldestufe {all_lvls.get(town)} {town} - {now}"
        else:
            msg['Subject'] = f"-WASSERALARM- Meldestufe {all_lvls.get(town)} {town} - {now}"
        msg['From'] = f'{homename} <{sender_email}>'
        msg['To'] = ','.join(receiver_email)

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
