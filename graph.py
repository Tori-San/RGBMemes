import json


class Edge:
    def __init__(self, env, source, target):
        self.env = env

        source_code = compile(source, '<string>', 'eval')
        self.source_node = env[source_code.co_names[0]]

        target_code = compile(target, '<string>', 'eval')
        self.target_node = env[target_code.co_names[0]]

        self.code = compile(f'{target} = {source}', '<string>', 'exec')

    def exec(self):
        exec(self.code, self.env)


class Node:

    def __init__(self, id):
        self.id = id

        self.out_edges = set()

    def propagate(self):
        for edge in self.out_edges:
            edge.exec()
            edge.target_node.update()

    def update(self):
        pass

    # meta stuff

    __types = dict()

    @classmethod
    def type(cls, typename):
        def decorator(subcls):
            cls.__types[typename] = subcls
            return subcls

        return decorator

    @classmethod
    def json_hook(cls, sender, receiver):
        def hook(d):
            if 'type' in d and d['type'] in cls.__types:
                return cls.__types[d['type']](sender=sender, receiver=receiver, **d)
            return d

        return hook


def parse(s, sender, receiver):
    data = json.loads(s, object_hook=Node.json_hook(sender, receiver))
    env = {node.id: node for node in data['nodes']}

    for [source, target] in data['edges']:
        edge = Edge(env, source, target)

        edge.source_node.out_edges.add(edge)

    return data['nodes']


@Node.type('source')
class SourceNode(Node):
    def __init__(self, id, universe, receiver, **kwargs):
        del kwargs  # ignored

        super().__init__(id)
        self.universe = universe
        self.receiver = receiver

        self.state = (0,) * 513

        self.receiver.join_multicast(self.universe)

        @self.receiver.listen_on('universe', universe=self.universe)
        def handler(packet):
            self.state = (0,) + packet.dmxData
            self.propagate()

    def __getitem__(self, item):
        return self.state[item]


@Node.type('sink')
class SinkNode(Node):
    def __init__(self, id, universe, sender, **kwargs):
        del kwargs  # ignored

        super().__init__(id)
        self.universe = universe
        self.sender = sender

        self.state = [0] * 513

        self.sender.activate_output(self.universe)
        self.sender[self.universe].multicast = True

    def __setitem__(self, key, value):
        self.state[key] = value

    def update(self):
        super().update()
        self.sender[self.universe].dmx_data = tuple(self.state[1:])


@Node.type('python')
class PythonNode(Node):
    def __init__(self, id, inputs, outputs, code, **kwargs):
        del kwargs  # ignored

        object.__setattr__(self, 'inputs', inputs)  # necessary due to __setattr__
        super().__init__(id)

        self.outputs = outputs

        self.input_state = {input: None for input in self.inputs}
        self.output_state = {output: None for output in self.outputs}

        self.code = compile(code, '<string>', 'exec')

    def __getattr__(self, item):
        return self.output_state[item]

    def __setattr__(self, key, value):
        if key in self.inputs:
            self.input_state[key] = value
        else:
            object.__setattr__(self, key, value)

    def update(self):
        super().update()

        env = {input: self.input_state[input] for input in self.inputs}
        exec(self.code, env)
        for output in self.outputs:
            self.output_state[output] = env.get(output)

        self.propagate()
