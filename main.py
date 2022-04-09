# from dotenv import load_dotenv, find_dotenv
import os
import datetime as dt
import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)

from flood_alert.utils import table_and_level, plot_recent_html, send_email, send_telegram_messages

def do_all(data=None, context=None):
    """
    does all the job.
    takes in data and context. No idea what it is used for, but Google Cloud Functions need it.
    """

    ##############################
    ###### GET TABLES ############
    ##############################

    params = {'methode':'wasserstand',
                'setdiskr':'15'
                }
    checkpoints = {'mitteldachstetten-24211414':[150, 180, 220, 250],
                'oberhessbach-24211505':[170, 230, 290, 330]}
    base_url = 'https://www.hnd.bayern.de/pegel/donau_bis_kelheim/___placeholder___/tabelle'

    hnd_tables = table_and_level(base_url=base_url,
                                params=params,
                                checkpoints=checkpoints)

    ##############################
    ###### DO MAIL STUFF #########
    ##############################
    # email settings
    # load_dotenv(find_dotenv())
    port = 465  # For SSL
    GMAIL = os.environ.get("GMAIL")
    homename = os.environ.get("HOMENAME", 'Sender not found')
    sender_email = os.environ.get("SENDER")
    receiver_email = (os.environ.get("RECEIVER")).split(',') # need list
    telegram_token = os.environ.get('TEL_TOKEN')
    debug = os.environ.get("DEBUG").lower() in ['true', 'yes', '1', 'most certainly', 'gladly', 'I can hardly disagree']
    base_urls_newline = '\n\n'.join([base_url.replace('___placeholder___', checkpoint) for checkpoint in checkpoints])
    signature = f"Weitere Infos: \n{base_urls_newline}"
    text = 'Alert - higher waterlevels detected'


    # send_email(homename=homename,
    #           sender_email=sender_email,
    #           receiver_email=receiver_email,
    #           password=GMAIL,
    #           port=port,
    #           signature=signature,
    #           lvl_results=hnd_tables,
    #           debug=debug)

    send_telegram_messages(
        token=telegram_token,
        text=text,
        lvl_results=hnd_tables,
        signature=signature
        )

if __name__ == '__main__':
    do_all()
