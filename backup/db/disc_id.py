import yaml


class DiscId:
    def __init__(self, db_id):
        self.db_id = db_id

    def serialize(self, out_file):
        with open(out_file, 'w') as f:
            yaml.dump(self, f)

    @staticmethod
    def deserialize(in_file):
        with open(in_file, 'r') as stream:
            return yaml.load(stream, Loader=yaml.FullLoader)
