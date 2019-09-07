import sacn
import graph

sender = sacn.sACNsender()
receiver = sacn.sACNreceiver()


if __name__ == '__main__':

    with open('g.json', 'r') as f:
        graph.parse(f.read(), sender, receiver)

    sender.start()
    receiver.start()

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    receiver.stop()
    sender.stop()
