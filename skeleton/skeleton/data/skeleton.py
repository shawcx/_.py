
import os
import typing
import uuid

import _

import skeleton

class skel:
    field1 : str = _.data.pkey()
    field2 : int = 100 # _.data.uniq(100)
    #field2 : int = _.data.uniq(100)
    field3 : int
    lat    : float #= _.data.uniq('geo')
    lng    : float #= _.data.uniq('geo')

@_.data.no_handler
class exo:
    class sub:
        v : int = 0
    s : sub
    u : uuid.UUID

@_.data.no_table
class custom:
    field1 : str
    field2 : int = 100
    field3 : int = None


@_.data.handles(custom)
class custom_handler:
    async def get(self, record_id=None):
        if not record_id:
            records = []
            for d in ['a','b','c']:
                r = _.data.custom()
                r.field1=d
                r.field3=ord(d)
                records.append(r._as_dict())
            self.write({'data':records})
        else:
            record = _.data['custom']()
            record.field1=record_id
            record.field3=200
            self.write(record._as_dict())
