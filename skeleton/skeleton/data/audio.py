
import _

import skeleton


@_.data.no_db
class audio:
    device    : str = _.data.uniq(_.data.pkey())
    frequency : int = 48000
    bits      : int = 16
    samples   : int = _.data.uniq()

    @_.auth.protected
    def get(self, record, record_id):
        if not record_id:
            records = []
            for d in ['a','b','c']:
                r = _.data.audio(device=d, samples=2048)
                records.append(r._asdict())
            self.write({'data':records})
        else:
            record = _.data['audio'](device=record_id,samples=2048)
            self.write(record.dump())


@_.data.no_handler
@_.data.no_pkey
class ignored:
    __no_handler = True
    __no_pkey    = True

    test : int = 100
