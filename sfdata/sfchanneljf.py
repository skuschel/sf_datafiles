from types import SimpleNamespace
from .sfchannel import SFChannel


class SFChannelJF(SFChannel):

    def __init__(self, name, group):
        self.name = name
        self._group = group
        self.datasets = SimpleNamespace(
            data = self._group,
            pids = self._group["pulse_id"]
        )
        self.reset_valid()

    @property
    def shape(self):
        nimages = self.nvalid
        juf = self._group
        image_shape = juf.handler.get_shape_out(juf.gap_pixels, juf.geometry)
        shape = (nimages, *image_shape)
        return shape


