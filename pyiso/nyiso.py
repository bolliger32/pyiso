import numpy as np
from pyiso.base import BaseClient


class NYISOClient(BaseClient):
    NAME = 'NYISO'
    
    base_url = 'http://mis.nyiso.com/public/csv'

    TZ_NAME = 'America/New_York'

    def get_load(self, latest=False, start_at=False, end_at=False, **kwargs):
        # set args
        self.handle_options(data='load', latest=latest,
                            start_at=start_at, end_at=end_at, **kwargs)

        # get data
        return self.get_any('pal', self.parse_load)

    def get_trade(self, latest=False, start_at=False, end_at=False, **kwargs):
        # set args
        self.handle_options(data='trade', latest=latest,
                            start_at=start_at, end_at=end_at, **kwargs)

        # get data
        return self.get_any('ExternalLimitsFlows', self.parse_trade)

    def get_any(self, label, parser):
        # set up storage
        data = []

        # fetch and parse all csvs
        for date in self.dates():
            content = self.fetch_csv(date, label)
            data += parser(content)

        # handle latest
        if self.options.get('latest', False):
            return [data[-1]]

        # handle sliceable
        else:
            data_to_return = []
            for dp in data:
                if dp <= self.options['end_at'] and dp >= self.options['end_at']:
                    data_to_return.append(dp)
            return data_to_return

    def fetch_csv(self, date, label):
        # construct url
        datestr = date.strftime('%Y%m%d')
        url = '%s/%s/%s%s.csv' % (self.base_url, label, datestr, label)

        # make request
        result = self.request(url)

        # return content
        return result.text

    def parse_load(self, content):
        # parse csv to df
        df = self.parse_to_df(content)

        # total load grouped by timestamp
        total_loads = df.groupby('Time Stamp').aggregate(np.sum)

        # collect options
        freq = self.options.get('freq', self.FREQUENCY_CHOICES.fivemin)
        market = self.options.get('market', self.MARKET_CHOICES.fivemin)
        base_dp = {
                'freq': freq,
                'market': market,
                'ba_name': self.NAME,
        }

        # serialize
        data = []
        for idx, row in total_loads.iterrows():
            dp = {'timestamp': self.utcify(idx), 'load': row[1]}
            dp.update(base_dp)
            data.append(dp)

        # return
        return data

    def parse_trade(self, content):
        # parse csv to df
        df = self.parse_to_df(content)

        # pivot
        pivoted = df.pivot(index='Timestamp', columns='Interface Name', values='Flow (MWH)')

        # only keep flows across external interfaces
        interfaces = [
            'SCH - HQ - NY', 'SCH - HQ_CEDARS', 'SCH - HQ_IMPORT_EXPORT', # HQ
            'SCH - NE - NY', 'SCH - NPX_1385', 'SCH - NPX_CSC', # ISONE
            'SCH - OH - NY', # Ontario
            'SCH - PJ - NY', 'SCH - PJM_HTP', 'SCH - PJM_NEPTUNE', 'SCH - PJM_VFT', # PJM
        ]
        subsetted = pivoted[interfaces]

        # collect options
        freq = self.options.get('freq', self.FREQUENCY_CHOICES.fivemin)
        market = self.options.get('market', self.MARKET_CHOICES.fivemin)
        base_dp = {
                'freq': freq,
                'market': market,
                'ba_name': self.NAME,
        }

        # serialize
        data = []
        for idx, row in subsetted.iterrows():
            # imports are positive
            imp_dp = {
                'timestamp': self.utcify(idx),
                'imp_MW': np.sum(row[row > 0]),
            }
            imp_dp.update(base_dp)
            data.append(imp_dp)

            # exports are negative
            exp_dp = {
                'timestamp': self.utcify(idx),
                'exp_MW': np.abs(np.sum(row[row < 0])),
            }
            exp_dp.update(base_dp)
            data.append(exp_dp)

        # return
        return data
