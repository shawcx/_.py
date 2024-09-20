
import _

from . import Skeleton_pb2


#@_.proto.handler(Skeleton_pb2.Skeleton)
class Skeleton:
    async def get(self, record, record_id):
        await super().get(record, record_id)
