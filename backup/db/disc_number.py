import yaml


class DiscNumber:
    def __init__(self, db_id, number):
        self.db_id = db_id
        self.number = number

    def serialize(self, out_file):
        with open(out_file, 'w') as f:
            yaml.dump(self, f)

    @staticmethod
    def deserialize(in_file):
        with open(in_file, 'r') as stream:
            return yaml.load(stream, Loader=yaml.FullLoader)
