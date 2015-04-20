__author__ = 'Robert Cope'

import time

import usb1

from PyHT6022.HantekFirmware import device_firmware


class Oscilloscope(object):
    ALT_VENDOR_ID = 0x04B4
    VENDOR_ID = 0x04B5
    MODEL_ID = 0x6022

    UPLOAD_FIRMWARE_REQUEST = 0xa0
    UPLOAD_FIRMWARE_INDEX = 0x00

    RW_CALIBRATION_REQUEST = 0xa2
    RW_CALIBRATION_VALUE = 0x08
    RW_CALIBRATION_INDEX = 0x00

    SET_SAMPLE_RATE_REQUEST = 0xe2
    SET_SAMPLE_RATE_VALUE = 0x00
    SET_SAMPLE_RATE_INDEX = 0x00

    SET_CH1_VR_REQUEST = 0xe0
    SET_CH1_VR_VALUE = 0x00
    SET_CH1_VR_INDEX = 0x00

    SET_CH2_VR_REQUEST = 0xe1
    SET_CH2_VR_VALUE = 0x00
    SET_CH2_VR_INDEX = 0x00

    SAMPLE_RATES = {0: ("48 MS/s", 48e6),
                    1: ("48 MS/s", 48e6),
                    2: ("48 MS/s", 48e6),
                    3: ("48 MS/s", 48e6),
                    4: ("48 MS/s", 48e6),
                    5: ("48 MS/s", 48e6),
                    6: ("48 MS/s", 48e6),
                    7: ("48 MS/s", 48e6),
                    8: ("48 MS/s", 48e6),
                    9: ("48 MS/s", 48e6),
                    10: ("48 MS/s", 48e6),
                    11: ("16 MSa/s", 16e6),
                    12: ("8 MSa/s", 8e6),
                    13: ("4 MSa/s", 4e6),
                    14: ("1 MS/s", 1e6),
                    15: ("1 MS/s", 1e6),
                    16: ("1 MS/s", 1e6),
                    17: ("1 MS/s", 1e6),
                    18: ("1 MS/s", 1e6),
                    19: ("1 MS/s", 1e6),
                    20: ("1 MS/s", 1e6),
                    21: ("1 MS/s", 1e6),
                    22: ("1 MS/s", 1e6),
                    23: ("1 MS/s", 1e6),
                    24: ("1 MS/s", 1e6),
                    25: ("500 KSa/s", 500e3),
                    26: ("200 KSa/s", 200e3),
                    27: ("100 KSa/s", 100e3)}

    VOLTAGE_RANGES = {0x01: ('+/- 5V', 0.0390625, 2.5),
                      0x02: ('+/- 2.5V', 0.01953125, 1.25),
                      0x05: ('+/- 1V', 0.0078125, 0.5),
                      0x0a: ('+/- 500mV', 0.00390625, 0.25)}

    def __init__(self, scope_id=0):
        self.device = None
        self.device_handle = None
        self.context = None
        self.scope_id = scope_id

    def setup(self):
        """
        Attempt to find a suitable scope to run.
        :return: True if a 6022BE scope was found, False otherwise.
        """
        self.context = usb1.USBContext()
        self.device = self.context.getByVendorIDAndProductID(self.VENDOR_ID, self.MODEL_ID, skip_on_error=True,
                                                             skip_on_access_error=True) or \
            self.context.getByVendorIDAndProductID(self.ALT_VENDOR_ID, self.MODEL_ID, skip_on_error=True,
                                                   skip_on_access_error=True)

        if not self.device:
            return False
        return True

    def open_handle(self):
        """
        Open a device handle for the scope. This needs to occur before sending any commands.
        :return: True if successful, False otherwise. May raise various libusb exceptions on fault.
        """
        if self.device_handle:
            return True
        if not self.device or not self.setup():
            return False
        self.device_handle = self.device.open()
        if self.device_handle.kernelDriverActive(0):
            self.device_handle.detachKernelDriver(0)
        self.device_handle.claimInterface(0)
        return True

    def close_handle(self, release_interface=True):
        """
        Close the current scope device handle. This should always be called at clean-up.
        :param release_interface: (OPTIONAL) Attempt to release the interface, if we still have it.
        :return: True if successful. May assert or raise various libusb errors if something went wrong.
        """
        if not self.device_handle:
            return True
        if release_interface:
            self.device_handle.releaseInterface(0)
        self.device_handle.close()
        self.device_handle = None
        return True

    def __del__(self):
        self.close_handle()

    def flash_firmware(self, firmware=device_firmware, timeout=60):
        """
        Flash scope firmware to the target scope device. This needs to occur once when the device is first attached,
        as the 6022BE does not have any persistant storage.
        :param firmware: (OPTIONAL) The firmware packets to send. Default: Stock firmware.
        :param timeout: (OPTIONAL) A timeout for each packet transfer on the firmware upload. Default: 60 seconds.
        :return: True if successful. May assert or raise various libusb errors if something went wrong.
        """
        if not self.device_handle:
            assert self.open_handle()
        for packet in firmware:
            bytes_written = self.device_handle.controlWrite(0x40, self.UPLOAD_FIRMWARE_REQUEST,
                                                            packet.value, self.UPLOAD_FIRMWARE_INDEX,
                                                            packet.data, timeout=timeout)
            assert bytes_written == packet.size
        # After firmware is written, scope will typically show up again as a different device, so scan again
        time.sleep(0.1)
        self.close_handle(release_interface=False)
        self.setup()
        self.open_handle()
        return True

    def get_calibration_values(self, timeout=0):
        """
        Retrieve the current calibration values from the oscilloscope.
        :param timeout: (OPTIONAL) A timeout for the transfer. Default: 0 (No timeout)
        :return: A 32 single byte int list of calibration values, if successful.
                 May assert or raise various libusb errors if something went wrong.
        """
        if not self.device_handle:
            assert self.open_handle()
        cal_string = self.device_handle.controlRead(0x40, self.RW_CALIBRATION_REQUEST, self.RW_CALIBRATION_VALUE,
                                                    self.RW_CALIBRATION_INDEX, 0x20, timeout=timeout)
        return map(ord, cal_string)

    def set_calibration_values(self, cal_list, timeout=0):
        """
        Set the a calibration level for the oscilloscope.
        :param cal_list: The list of calibration values, should usually be 32 single byte ints.
        :param timeout: (OPTIONAL) A timeout for the transfer. Default: 0 (No timeout)
        :return: True if successful. May assert or raise various libusb errors if something went wrong.
        """
        if not self.device_handle:
            assert self.open_handle()
        cal_list = cal_list if isinstance(cal_list, basestring) else "".join(map(chr, cal_list))
        data_len = self.device_handle.controlWrite(0x40, self.RW_CALIBRATION_REQUEST, self.RW_CALIBRATION_VALUE,
                                                   self.RW_CALIBRATION_INDEX, cal_list, timeout=timeout)
        assert data_len == len(cal_list)
        return True

    def read_data(self, data_size=0x400, raw=False, timeout=0):
        """
        Read both channel's ADC data from the device. No trigger support, you need to do this in software.
        :param data_size: (OPTIONAL) The number of data points for each channel to retrieve. Default: 0x400 points.
        :param raw: (OPTIONAL) Return the raw bytestrings from the scope. Default: Off
        :param timeout: (OPTIONAL) The timeout for each bulk transfer from the scope. Default: 0 (No timeout)
        :return: If raw, two bytestrings are returned, the first for CH1, the second for CH2. If raw is off, two
                 lists are returned (by iterating over the bytestrings and converting to ordinals). The lists contain
                 the ADC value measured at that time, which should be between 0 - 255.

                 If you'd like nicely scaled data, just dump the return lists into the scale_read_data method which
                 your current voltage range setting.

                 This method may assert or raise various libusb errors if something went wrong.
        """
        data_size <<= 0x1
        if not self.device_handle:
            assert self.open_handle()
        self.device_handle.controlRead(0x40, 0xe3, 0x00, 0x00, 0x01, timeout=timeout)
        data = self.device_handle.bulkRead(0x86, data_size, timeout=timeout)
        if raw:
            return data[::2], data[1::2]
        else:
            return map(ord, data[::2]), map(ord, data[1::2])

    def build_data_reader(self, raw=False):
        """
        Build a (slightly) more optimized reader closure, for (slightly) better performance.
        :param raw: (OPTIONAL) Return the raw bytestrings from the scope. Default: Off
        :return: A fast_read_data function, which behaves much like the read_data function. The fast_read_data
                 function returned takes two parameters:
                 :param data_size: Number of data points to return (1 point <-> 1 byte).
                 :param timeout: (OPTIONAL) The timeout for each bulk transfer from the scope. Default: 0 (No timeout)
                 :return:  If raw, two bytestrings are returned, the first for CH1, the second for CH2. If raw is off,
                 two lists are returned (by iterating over the bytestrings and converting to ordinals).
                 The lists contain the ADC value measured at that time, which should be between 0 - 255.

        This method and the closure may assert or raise various libusb errors if something went/goes wrong.
        """
        if not self.device_handle:
            assert self.open_handle()
        scope_control_read = self.device_handle.controlRead
        scope_bulk_read = self.device_handle.bulkRead
        if raw:
            def fast_read_data(data_size, timeout=0):
                data_size <<= 0x1
                scope_control_read(0x40, 0xe3, 0x00, 0x00, 0x01, timeout)
                data = scope_bulk_read(0x86, data_size, timeout)
                return data[::2], data[1::2]
        else:
            def fast_read_data(data_size, timeout=0):
                data_size <<= 0x1
                scope_control_read(0x40, 0xe3, 0x00, 0x00, 0x01, timeout)
                data = scope_bulk_read(0x86, data_size, timeout)
                return map(ord, data[::2]), map(ord, data[1::2])
        return fast_read_data

    @staticmethod
    def scale_read_data(read_data, voltage_range, probe_multiplier=1):
        """
        Convenience function for converting data read from the scope to nicely scaled voltages.
        :param read_data: The list of points returned from the read_data functions.
        :param voltage_range: The voltage range current set for the channel.
        :param probe_multiplier: (OPTIONAL) An additonal multiplictive factor for changing the probe impedance.
                                 Default: 1
        :return: A list of correctly scaled voltages for the data.
        """
        scale_factor = (5.0 * probe_multiplier)/(voltage_range << 7)
        return [(datum - 128)*scale_factor for datum in read_data]

    def set_sample_rate(self, rate_index, timeout=0):
        """
        Set the sample rate index for the scope to sample at. This determines the time between each point the scope
        returns.
        :param rate_index: The rate_index. These are the keys for the SAMPLE_RATES dict for the Oscilloscope object.
                           Common rate_index values and actual sample rate:
                           0    <->     48  MS/s
                           11   <->     16  MS/s
                           12   <->     8   MS/s
                           13   <->     4   MS/s
                           14   <->     1   MS/s
                           25   <->     500 KS/s
                           26   <->     200 KS/s
                           27   <->     100 KS/s

                           Outside of the range spanned by these values, and those listed in the SAMPLE_RATES dict, it
                           is not know how a value such as 28 or 29 will affect the behavior of the scope.
        :param timeout: (OPTIONAL) An additonal multiplictive factor for changing the probe impedance.
        :return: True if successful. This method may assert or raise various libusb errors if something went wrong.
        """
        if not self.device_handle:
            assert self.open_handle()
        bytes_written = self.device_handle.controlWrite(0x40, self.SET_SAMPLE_RATE_REQUEST,
                                                        self.SET_SAMPLE_RATE_VALUE, self.SET_SAMPLE_RATE_INDEX,
                                                        chr(rate_index), timeout=timeout)
        assert bytes_written == 0x01
        return True

    def convert_sampling_rate_to_measurement_times(self, num_points, rate_index):
        """
        Convenience method for converting a sampling rate index into a list of times from beginning of data collection
        and getting human-readable sampling rate string.
        :param num_points: The number of data points.
        :param rate_index: The sampling rate index used for data collection.
        :return: A list of times in seconds from beginning of data collection, and the nice human readable rate label.
        """
        rate_label, rate = self.SAMPLE_RATES.get(rate_index, ("? MS/s", 1.0))
        return [i/rate for i in xrange(num_points)], rate_label

    def set_ch1_voltage_range(self, range_index, timeout=0):
        """
        Set the voltage scaling factor at the scope for channel 1 (CH1).
        :param range_index: A numerical constant, which determines the devices range by the following formula:
                            range := +/- 5.0 V / (range_indeX).

                            The stock software only typically uses the range indicies 0x01, 0x02, 0x05, and 0x0a,
                            but others, such as 0x08 and 0x0b seem to work correctly.

                            This same range_index is given to the scale_read_data method to get nicely scaled
                            data in voltages returned from the scope.

        :param timeout: (OPTIONAL) An additonal multiplictive factor for changing the probe impedance.
        :return: True if successful. This method may assert or raise various libusb errors if something went wrong.
        """
        if not self.device_handle:
            assert self.open_handle()
        bytes_written = self.device_handle.controlWrite(0x40, self.SET_CH1_VR_REQUEST,
                                                        self.SET_CH1_VR_VALUE, self.SET_CH1_VR_INDEX,
                                                        chr(range_index), timeout=timeout)
        assert bytes_written == 0x01
        return True

    def set_ch2_voltage_range(self, range_index, timeout=0):
        """
        Set the voltage scaling factor at the scope for channel 1 (CH1).
        :param range_index: A numerical constant, which determines the devices range by the following formula:
                            range := +/- 5.0 V / (range_indeX).

                            The stock software only typically uses the range indicies 0x01, 0x02, 0x05, and 0x0a,
                            but others, such as 0x08 and 0x0b seem to work correctly.

                            This same range_index is given to the scale_read_data method to get nicely scaled
                            data in voltages returned from the scope.

        :param timeout: (OPTIONAL) An additonal multiplictive factor for changing the probe impedance.
        :return: True if successful. This method may assert or raise various libusb errors if something went wrong.
        """
        if not self.device_handle:
            assert self.open_handle()
        bytes_written = self.device_handle.controlWrite(0x40, self.SET_CH2_VR_REQUEST,
                                                        self.SET_CH2_VR_VALUE, self.SET_CH2_VR_INDEX,
                                                        chr(range_index), timeout=timeout)
        assert bytes_written == 0x01
        return True