from nostr.relay_manager import RelayManager
from nostr.message_type import ClientMessageType
from nostr.filter import Filter, Filters
from nostr.event import Event
from nostr.key import PrivateKey
from os.path import exists
from secrets import token_hex

import time
import json 
import ssl

with open("data/relays.json", "r") as relaysFile:
    relays = json.load(relaysFile)

def publish(key: PrivateKey, public_key: str, data: dict) -> dict:
    relay_manager = RelayManager()
    for relay in relays:
        relay_manager.add_relay(relay)
    
    relay_manager.open_connections({"cert_reqs": ssl.CERT_NONE})
    time.sleep(1)
    
    message = key.encrypt_message(message=json.dumps(data), public_key_hex=public_key)
    message = json.dumps({"data": message, "type": "emperor"})

    event = Event(public_key=key.public_key.hex(), content=message, kind=892)
    key.sign_event(event)
    while True:
        try:
            relay_manager.publish_event(event)
            break
        except KeyboardInterrupt:
            exit()
        except:
            continue
    
    relay_manager.close_connections()
    return { "publish_id": event.id }

def subscribe(key: PrivateKey, public_key: str, event_id: str):
    identity = token_hex(5)
    
    filters = Filters([Filter(
        event_ids=[event_id],
        authors=[public_key], 
        kinds=[892]
    )])
    request = [ClientMessageType.REQUEST, identity]
    request.extend(filters.to_json_array())

    relay_manager = RelayManager()
    for relay in relays:
        relay_manager.add_relay(relay)
    
    relay_manager.add_subscription(identity, filters)
    relay_manager.open_connections({"cert_reqs": ssl.CERT_NONE})
    time.sleep(2)
    
    message = json.dumps(request)
    while True:
        try:
            relay_manager.publish_message(message)
            break
        except KeyboardInterrupt:
            exit()
        except:
            pass
    
    time.sleep(1)
    while relay_manager.message_pool.has_events():
        try:
            content = relay_manager.message_pool.get_event().event.content
            content = json.loads(content)
        except KeyboardInterrupt:
            exit()
        except:
            continue
        
        if (content.get("type") == "emperor"):
            content = key.decrypt_message(content["data"], key.public_key.hex())
            
    relay_manager.close_connections()

def main():
    if not (exists("keychain.key") == True):
        key = PrivateKey()
        pub = key.public_key
        with open("keychain.key", "w") as w:
            json.dump({
                "key": key.bech32(), 
                "pub": pub.bech32()
            }, w)
    else:
        with open("keychain.key", "r") as r:
            data = json.load(r)

        key = PrivateKey.from_nsec(data["key"])
        pub = key.public_key.from_npub(data["pub"])