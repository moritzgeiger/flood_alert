from dotenv import load_dotenv, find_dotenv
import os
import datetime as dt

from flood_alert.utils import table_and_level
from flood_alert.send_mail import update_campaign

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
    load_dotenv(find_dotenv())
    debug = os.environ.get("DEBUG").lower() in ['true', 'yes', '1', 'most certainly', 'gladly', 'I can hardly disagree']
    signature = f"<p>Weitere Infos: <br>-{'<br>-'.join([base_url.replace('___placeholder___', checkpoint) for checkpoint in checkpoints])}</p>"
    campaign_id = 6

    if any([x.get('alert_lvl') > 1 for x in hnd_tables.values()]) or debug:
        print('there is an alert!')
        update_campaign(campaign_id=campaign_id,
                        signature=signature,
                        lvl_results=hnd_tables,
                        debug=debug)

        # update_campaign(homename=homename,
                  # sender_email=sender_email,
                  # receiver_email=receiver_email,
                  # password=GMAIL,
                  # port=port,
                  # signature=signature,
                  # lvl_results=hnd_tables,
                  # debug=debug)
    else:
      _ = [print(f'There was no alert at {id_}') for id_ in hnd_tables.keys()]
      print('Exit function without sending mail.')

if __name__ == '__main__':
    do_all()
