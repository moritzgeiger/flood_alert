from dotenv import load_dotenv, find_dotenv
import os
import datetime as dt

from flood_alert.utils import pd_table, plot_today_html, send_mail, compile_email, alert


##############################
###### GET TABLES ############
##############################

# GKD
url_gkd = 'https://www.gkd.bayern.de/de/fluesse/wasserstand/kelheim/mitteldachstetten-24211414/messwerte/tabelle'
params_gkd = {
#               'addhr':'hr_w_hw',
#               'beginn':now
             }
alert_levels_gkd = {'gkd_stufe_1': 150,
                    'gkd_stufe_2': 180,
                    'gkd_stufe_3': 220,
                    'gkd_stufe_4': 250}

gkd_table = pd_table(base_url=url_gkd,
                     params=params_gkd,
                     alert_levels=alert_levels_gkd)

# HND
params_hnd = {'methode':'wasserstand',
              'setdiskr':'15',
    #           'addhr':'hr_ms',
    #           'vhs_type':'std',
    #           'end':now, #09.07.2021
             }
url_hnd = 'https://www.hnd.bayern.de/pegel/donau_bis_kelheim/ansbach-24211651/tabelle'
alert_levels_hnd = {'hnd_stufe_1' : 220,
                    'hnd_stufe_2' : 280,
                    'hnd_stufe_3' : 340,
                    'hnd_stufe_4' : 400}

hnd_table = pd_table(base_url=url_hnd,
                     params=params_hnd,
                     alert_levels=alert_levels_hnd)



##############################
###### DO MAIL STUFF #########
##############################
# email settings
load_dotenv(find_dotenv())
port = 465  # For SSL
GMAIL = os.environ.get("GMAIL")

# email contents
homename = 'Wasserzeller Muehle'
sender_email = os.environ.get("SENDER")
receiver_email = os.environ.get("RECEIVER")
signature = f"<p>Sources: <br>- {url_hnd} <br>- {url_gkd}</p>"

msg = compile_email(homename=homename,
                    sender_email=sender_email,
                    receiver_email=receiver_email,
                    signature=signature,
                    df=hnd_table,
                    alert_levels=alert_levels_hnd,
                    )

def do_all(event, context):
  if alert(hnd_table):
      send_mail(port=port,
              password=GMAIL,
              receiver_email=receiver_email,
              message=msg.as_string(),
              sender_email=sender_email)
