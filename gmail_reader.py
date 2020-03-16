import pickle
import os.path
import email
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from bs4 import BeautifulSoup
import base64
from googleapiclient.errors import HttpError
import html2text
from formatflowed import convertToWrapped

# source 1 https://github.com/abhishekchhibber/Gmail-Api-through-Python/blob/master/gmail_read.py
# source 2 https://gist.github.com/ktmud/cb5e3ca0222f86f5d0575caddbd25c03
# TODO: -- solve problem with flowed type
#      -- refractor this shit-code
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def GetMimeMessage(service, user_id, msg_id):
    """Get a Message and use it to create a MIME Message.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      msg_id: The ID of the Message required.

    Returns:
      A MIME Message, consisting of data from Message.
    """
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id,
                                                 format='raw').execute()

        # print('Message snippet: %s' % message['snippet'])
        msg_str = base64.urlsafe_b64decode(message['raw'].encode('utf-8'))
        mime_msg = email.message_from_string(msg_str.decode("utf-8", errors='replace'))

        return mime_msg
    except HttpError as error:
        print(f'An error occurred: {error}')


def GetContentfromMessage(payld):
    mssg_parts = payld['parts']  # fetching the message parts
    part_one = mssg_parts[0]  # fetching first element of the part
    try:
        part_body = part_one['body']  # fetching body of the message
        part_data = part_body['data']  # fetching data from the body
        clean_one = part_data.replace("-", "+")  # decoding from Base64 to UTF-8
        clean_one = clean_one.replace("_", "/")  # decoding from Base64 to UTF-8
        clean_two = base64.b64decode(bytes(clean_one, 'UTF-8'))  # decoding from Base64 to UTF-8
        soup = BeautifulSoup(clean_two, "lxml")
        mssg_body = soup.body()
        return mssg_body
    except KeyError:
        return None
    # mssg_body is a readible form of message body
    # depending on the end user's requirements, it can be further cleaned
    # using regex, beautiful soup, or any other method


def GetMessage(service, user_id, msg_id):
    """Get a Message with given ID.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      msg_id: The ID of the Message required.

    Returns:
      A Message.
    """
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()

        # print('Message snippet: %s' % message['snippet'])

        return message
    except HttpError as error:
        print(f'An error occurred: {error}')


def ListMessagesWithLabels(service, user_id, label_ids=[]):
    """List all Messages of the user's mailbox with label_ids applied.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      label_ids: Only return Messages with these labelIds applied.

    Returns:
      List of Messages that have all required Labels applied. Note that the
      returned list contains Message IDs, you must use get with the
      appropriate id to get the details of a Message.
    """
    try:
        response = service.users().messages().list(userId=user_id,
                                                   labelIds=label_ids).execute()
        messages = []
        if 'messages' in response:
            messages.extend(response['messages'])

        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = service.users().messages().list(userId=user_id,
                                                       labelIds=label_ids,
                                                       pageToken=page_token).execute()
            messages.extend(response['messages'])
        return messages
    except HttpError as e:
        print(e.content)


def extract_body(msg, depth=0):
    """ Extract content body of an email messsage """
    body = []
    if msg.is_multipart():
        main_content = None
        # multi-part emails often have both
        # a text/plain and a text/html part.
        # Use the first `text/plain` part if there is one,
        # otherwise take the first `text/*` part.
        for part in msg.get_payload():
            is_txt = part.get_content_type() == 'text/plain'
            if not main_content or is_txt:
                main_content = extract_body(part)
            if is_txt:
                break
        if main_content:
            body.extend(main_content)
    elif msg.get_content_type().startswith("text/"):
        # Get the messages
        # charset = msg.get_param('charset', 'utf-8').lower()
        # update charset aliases
        # charset = email.charset.ALIASES.get(charset, charset)
        # msg.set_param('charset', charset)

        if msg.get_content_type() == "text/plain":
            try:

                # clean_one = base64_info.replace("-", "+")  # decoding from Base64 to UTF-8
                # clean_one = clean_one.replace("_", "/")  # decoding from Base64 to UTF-8
                # print("original : ", clean_one)
                code = msg.get_params()[1][1]
                if code == 'flowed':
                    clean_two = msg.get_payload()
                else:
                    base64_info = msg.get_payload(decode=True)
                    clean_two = base64_info.decode(code)
                # if msg["Content-Transfer-Encoding"] == "base64":
                #     clean_two = base64.urlsafe_b64decode(clean_one).decode(code)  # decoding from Base64 to UTF-8
                # else:
                print(f"\n8////////////////\n{code}\n////////////////8\n")
                #     clean_two = quopri.decodestring(clean_one).decode(code)
                body.append(clean_two)
            except AssertionError as e:
                print('Parsing failed.    ')
                print(e)
            except LookupError:
                # set all unknown encoding to utf-8
                # then add a header to indicate this might be a spam
                msg.set_param('charset', 'utf-8')
                body.append('=== <UNKOWN ENCODING POSSIBLY SPAM> ===')
                body.append(msg.get_content())
            except AttributeError:
                print(msg)
        elif msg.get_content_type() == "text/html":
            base64_info = msg.get_payload()
            text = html2text.html2text(base64_info)
            body.append(text)
            # body.append(base64_info)
        else:
            raise TypeError("Unsupportable type")
    return body


def main():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)
    # Call the Gmail API
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    if not labels:
        print('No labels found.')
    else:
        print('Labels:')
        for label in labels:
            print(label['name'])
    for message_id in ListMessagesWithLabels(service, 'me', ["INBOX"]):
        answer = GetMimeMessage(service, 'me', message_id["id"])
        print("------------/-/-/------------------------//-------------------/-/-/")
        print(extract_body(answer)[0])
        print("------------/-/-/------------------------//-------------------/-/-/")


if __name__ == '__main__':
    main()
