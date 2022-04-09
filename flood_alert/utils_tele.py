import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import datetime as dt
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from io import BytesIO, StringIO
import tempfile
from os.path import basename
import re
from google.cloud import storage
import logging


BUCKET = os.environ.get("BUCKET")

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

def plot_recent_html(df, lvls, local=None, bucket_name=None):
    """
    Returns the water level plot as embed html filtered to the last 12 hours.
    Returns either cloud embed img or temp bytes file.
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

    # decide to store plot in cloud
    if local:
        filepath = f'plot_{local}.png'
        fig.savefig(filepath, format='png')
        return filepath

    if bucket_name:
        logging.info(f'uploading to {bucket_name}')
        tmpfile = BytesIO()
        fig.savefig(tmpfile, format='png')
        now = dt.datetime.now().strftime('%Y%m%d%H%M%s%ms')
        # print(now)
        # upload to cloud and get url
        file_url = upload_file_gcp(source_file_bytes=tmpfile,
                                   file_name_uploaded=f'recent_dev_{now}.png',
                                   bucket_name=bucket_name,
                                   content_type='image/png')
        img_html =  f'<img src="{file_url}" alt="Wasserstandsentwicklung 12 Stunden">'
        tmpfile.close()
        # return img_html
        return file_url
        # embed code html

    # save plot as html locally as temp
    else:
        tmpfile = BytesIO()
        fig.savefig(tmpfile, format='png')
        encoded = base64.b64encode(tmpfile.getvalue()).decode('utf-8')
        plot_html = '<br><br>' + '<img src=\'data:image/png;base64,{}\'>'.format(encoded) + "<br><br>"
        return plot_html # embed code html

def send_telegram_messages(token, text, lvl_results, signature):
    """Sends telegram updates to @wassermeldung channel.
    """
    logging.info('send_telegram_message was called.')

    if any([x.get('alert_lvl') > 1 for x in lvl_results.values()]) or debug:

        url = f'https://api.telegram.org/bot{token}/sendMessage'
        params = {
            'chat_id': '@wassermeldung',
            'text': f'{text}'
        }
        # SEND INIT MSG
        r = requests.get(url, params=params)

        # SEND LEVELS
        names = ' and '.join([x.get('name') for key, x in lvl_results.items()])
        params = {
            'chat_id': '@wassermeldung',
            'text': f'At {names}'
        }
        r = requests.get(url, params=params)

        # SEND DETAIL
        # merge all html per checkpoint together
        plots_html = [plot_recent_html(vals.get('df'), vals.get('level_list'), bucket_name=BUCKET) for id_, vals in lvl_results.items()]

        for plot in plots_html:
            logging.info(plot)
            url_photo = f'https://api.telegram.org/bot{token}/sendPhoto'
            params = {
            'chat_id': '@wassermeldung',
            'photo': f'{plot}'
            }
            r_plots = requests.get(url_photo, params=params)

        alert_levels_html = [f"{i+1}. Meldestufe fuer {val.get('name').capitalize()}: {val.get('alert_lvl')}\n" \
                      for i, (key, val) in enumerate(lvl_results.items())]


        together = '\n'.join(alert_levels_html)
        logging.info(together)

        params = {
            'chat_id': '@wassermeldung',
            'text': f'{together}'
        }

        r_together = requests.get(url, params=params)

        # SEND LINKS
        params = {
            'chat_id': '@wassermeldung',
            'text': f'{signature}'
        }
        r_sig = requests.get(url, params=params)


    else:
      _ = [logging.info(f'There was no alert at {id_}') for id_ in lvl_results.keys()]
      logging.info('Exit function without sending message.')

