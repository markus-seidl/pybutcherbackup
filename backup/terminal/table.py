import texttable


class TableColumn:
    def __init__(self, name):
        self.name = name
        self.min_len = None
        self.max_len = None
        self.align = "l"
        self.type = "t"


class Table:
    def __init__(self, table_data: list, columns: [TableColumn]):
        self.table_data = table_data
        self.columns = columns

        min_len = [10000] * len(self.columns)
        max_len = [-1] * len(self.columns)

        for td in self.table_data:
            for i in range(len(self.columns)):
                str_len = len(str(td[i]))
                min_len[i] = min(min_len[i], str_len)
                max_len[i] = max(max_len[i], str_len)

        for i in range(len(self.columns)):
            c = self.columns[i]
            c.min_len = min_len[i]
            c.max_len = max_len[i]

    def print(self):
        table = texttable.Texttable()
        cols_align = list()
        cols_type = list()

        for c in self.columns:
            cols_align.append(c.align)
            cols_type.append(c.type)

        for row in self.table_data:
            table.add_row(row)

        print(table.draw())
