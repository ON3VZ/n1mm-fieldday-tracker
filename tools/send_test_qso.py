"""Send simulated N1MM UDP packets to the tracker — for testing without N1MM.

Examples (run from the project root):

    python tools/send_test_qso.py ON4BAF/P 3525.19          # log a QSO
    python tools/send_test_qso.py ON4BAF/P 3525.19 --mode SSB --station PC2
    python tools/send_test_qso.py ON4BAF/P 3525.19 --delete # delete it again
    python tools/send_test_qso.py ON4BAF/P 7020 --replace-call ON4CDZ/P
    python tools/send_test_qso.py --lookup ON4BAF/P 3525.19 # lookupinfo (moet genegeerd worden)

The QSO ID is derived from callsign+frequency so that a later --delete or
--replace-call targets the same record.
"""
import argparse
import hashlib
import socket
from datetime import datetime, timezone


def packet(tag, call, freq_khz, mode, station, qso_id, ts):
    rxfreq = int(round(freq_khz * 100))  # kHz → 10 Hz units
    return f"""<?xml version="1.0" encoding="utf-8"?>
<{tag}>
<app>N1MM</app>
<contestname>FDREG1</contestname>
<timestamp>{ts}</timestamp>
<mycall>ON6WL/P</mycall>
<band>3.5</band>
<rxfreq>{rxfreq}</rxfreq>
<txfreq>{rxfreq}</txfreq>
<mode>{mode}</mode>
<call>{call}</call>
<StationName>{station}</StationName>
<ID>{qso_id}</ID>
<IsClaimedQso>1</IsClaimedQso>
<IsOriginal>True</IsOriginal>
</{tag}>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("call")
    parser.add_argument("freq_khz", type=float)
    parser.add_argument("--mode", default="CW")
    parser.add_argument("--station", default="TEST-PC1")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=12060)
    parser.add_argument("--delete", action="store_true")
    parser.add_argument("--replace-call", metavar="NEWCALL")
    parser.add_argument("--lookup", action="store_true",
                        help="send a lookupinfo packet (tracker must ignore it)")
    args = parser.parse_args()

    qso_id = hashlib.sha1(f"{args.call}|{args.freq_khz}".encode()).hexdigest()[:32]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    if args.delete:
        data = (f'<?xml version="1.0" encoding="utf-8"?>\n<contactdelete>\n'
                f'<timestamp>{ts}</timestamp>\n<call>{args.call}</call>\n'
                f'<StationName>{args.station}</StationName>\n'
                f'<ID>{qso_id}</ID>\n</contactdelete>')
        label = "contactdelete"
    elif args.replace_call:
        data = packet("contactreplace", args.replace_call, args.freq_khz,
                      args.mode, args.station, qso_id, ts)
        label = f"contactreplace → {args.replace_call}"
    elif args.lookup:
        data = packet("lookupinfo", args.call, args.freq_khz,
                      args.mode, args.station, qso_id, ts)
        label = "lookupinfo (should be ignored)"
    else:
        data = packet("contactinfo", args.call, args.freq_khz,
                      args.mode, args.station, qso_id, ts)
        label = "contactinfo"

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(data.encode("utf-8"), (args.host, args.port))
    print(f"Sent {label} for {args.call} to {args.host}:{args.port} (ID {qso_id[:8]}…)")


if __name__ == "__main__":
    main()
