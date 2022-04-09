from __future__ import print_function
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from pprint import pprint
from dotenv import load_dotenv, find_dotenv
import os
from dotenv import load_dotenv, find_dotenv
import os
import datetime as dt
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# internal import
from flood_alert.utils import plot_recent_html, upload_csv

### ENV VARIABLES
load_dotenv(find_dotenv())
API_SIB = os.environ.get("API_SIB")
bucket_name = os.environ.get("BUCKET")

###### UPDATE EMAIL CONTENT #########
def update_campaign(campaign_id, signature, lvl_results, debug):
    """
    Updates an Email-Campaign with the sendinblue python SDK with the email.mime library.
    Takes in variables for the mail content [homename (str), lvl_results (dict), signature (str)]
    and settings to send the email [sender_email]
    There is a debug argument to test the email function despite a trigger isn't reached.
    """
    print('update_campaign was called.')
    # check, if there is alert level 2 was reached in the checkpoints
    # init msg
    init = "<p>***WASSERSTANDSALARM***, <br><br>Es wurde ein ueberhoehter Wasserstand gemeldet.<br><br></p>"

    # unpack dfs
    plots_html = [plot_recent_html(vals.get('df'), vals.get('level_list'), bucket_name=bucket_name) for id_, vals in lvl_results.items()]
    alert_levels_html = [f"<p><b>{i+1}. Meldestufe fuer {val.get('name').capitalize()}: {val.get('alert_lvl')}</b></p>" \
                          for i, (key, val) in enumerate(lvl_results.items())]

    # merge all html per checkpoint together
    together = '<br><br>'.join([f'{alert_levels_html[x]}\
                                    <br>{plots_html[x]}' for x in range(len(plots_html))])

    ### compile all variable content
    body = '<body>' + init + together + signature + '</body>'
    # print(body)
    # find the highest level
    all_lvls = {x.get('name'):x.get('alert_lvl') for x in lvl_results.values()}
    town = max(all_lvls, key=all_lvls.get)

    # compile email msg
    now = dt.datetime.now()
    soon = now + dt.timedelta(minutes=2)

    # avoid automized email ruling by subject when testing
    if debug:
        subject = f"-TESTALARM- Meldestufe {all_lvls.get(town)} {town} - {now.strftime('%y-%m-%d %H:%M')}"
        list_id = 2 # test recipients
    else:
        subject = f"-WASSERALARM- Meldestufe {all_lvls.get(town)} {town} - {now.strftime('%y-%m-%d %H:%M')}"
        list_id = 3 # real recipients

    ###### CONFIG SENDINBLUE #####
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = API_SIB
    api_instance = sib_api_v3_sdk.EmailCampaignsApi(sib_api_v3_sdk.ApiClient(configuration))

    ###### UPDATE CAMPAIGN #######
    email_campaign = sib_api_v3_sdk.UpdateEmailCampaign(html_content=body,
                                                        # scheduled_at=soon,
                                                        subject=subject,
                                                        inline_image_activation=True,
                                                        recurring=True, # can receive campaign several times
                                                        send_at_best_time=False,
                                                        recipients={"listIds": [list_id]},
                                                        ) # UpdateEmailCampaign | Values to update a campaign
    # Update an email campaign
    try:
        api_instance.update_email_campaign(campaign_id, email_campaign)
        print(f'email campaign {campaign_id} was updated.')

    except ApiException as e:
        print("Exception when calling EmailCampaignsApi->update_email_campaign: %s\n" % e)

    # send the updated email campaign
    try:
        api_instance.send_email_campaign_now(campaign_id)
        print(f'email campaign {campaign_id} was sent at {now.strftime("%y-%m-%d %H:%M")}')
    except ApiException as e:
        print("Exception when calling EmailCampaignsApi->send_email_campaign_now: %s\n" % e)
