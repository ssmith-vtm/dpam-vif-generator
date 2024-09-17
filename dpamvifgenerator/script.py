######################################################
# Copyright (c) VESA. All rights reserved.
# This code is licensed under the MIT License (MIT).
# THIS CODE IS PROVIDED *AS IS* WITHOUT WARRANTY OF
# ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING ANY
# IMPLIED WARRANTIES OF FITNESS FOR A PARTICULAR
# PURPOSE, MERCHANTABILITY, OR NON-INFRINGEMENT.
######################################################
import logging
from xml.etree import ElementTree as ET

from dpamvifgenerator.utility import XML_INDENT


# Exception Classes
class MissingGeneratorArg(Exception):
    pass


class InvalidInputVIF(Exception):
    pass


class InvalidSettingsXML(Exception):
    pass


# Progress Emitter Class
class Progress:
    def __init__(
        self,
        total: float,
        prefix: str = "",
        suffix: str = "",
        decimals: int = 1,
        length: int = 100,
        fill: str = "+",
        printEnd: str = "\r",
    ):
        """
        Call in a loop to create terminal progress bar
        @params:
            total       - Required  : total value of progress bar
            prefix      - Optional  : prefix string
            suffix      - Optional  : suffix string
            decimals    - Optional  : positive number of decimals in percent complete
            length      - Optional  : character length of bar
            fill        - Optional  : bar fill character
            printEnd    - Optional  : end character (e.g. "\r", "\r\n")
        """
        self.prefix = prefix
        self.suffix = suffix
        self.decimals = decimals
        self.length = length
        self.fill = fill
        self.printEnd = printEnd
        self.total = total

    # Progress Bar Printing Function
    def printProgressBar(self, value: int):
        percent = ("{0:." + str(self.decimals) + "f}").format(
            100 * (value / float(self.total))
        )
        filledLength = int(self.length * value // self.total)
        bar = self.fill * filledLength + "-" * (self.length - filledLength)
        print(f"\r{self.prefix} |{bar}| {percent}% {self.suffix}", end=self.printEnd)

    # Value updater
    def setValue(self, value: int):
        self.printProgressBar(value)
        if value == self.total:
            # Print newline to close out progress bar since total has been met
            print()


# DPAM VIF Generator Class
class DPAMVIFGenerator:
    def __init__(self, **kwargs):
        # Log parameters
        logging.info(
            f"Initializing DPAM VIF Generator with the following parameters: {kwargs}"
        )
        # Load arguments from user
        for key, value in kwargs.items():
            setattr(self, key, value)
        # Check for required args
        if not all(hasattr(self, key) for key in ["in_vif", "out_vif", "settings"]):
            error = "Error: Missing DPAMVIFGenerator argument: {}".format(key)
            logging.error(error)
            raise MissingGeneratorArg(error)
        # Check for passed in progress emitter
        if not hasattr(self, "progress"):
            # Create script's own progress emitter
            self.progress_object = Progress(100)
            self.progress = self.progress_object.setValue

    def generate_vif(self):
        # Set progress
        logging.info("Generating DPAM VIF XML File...")
        self.progress(0)

        # Register namespaces
        for name, namespace in DPAMVIFGenerator.get_prefix_map().items():
            ET.register_namespace(name, namespace)
        self.progress(10)

        # Load input USBIF VIF XML
        input_vif = DPAMVIFGenerator.load_input_vif(self.in_vif)
        self.progress(30)

        # Load DPAM Settings XML
        dpam_settings = DPAMVIFGenerator.load_dpam_settings(self.settings)
        self.progress(50)

        # Generate DPAM VIF XML file
        DPAMVIFGenerator.generate_dpam_vif(input_vif, dpam_settings)
        self.progress(80)

        # Write out generated XML file
        DPAMVIFGenerator.write_output_vif(input_vif, self.out_vif)
        self.progress(100)
        logging.info("Generation Complete")

    @staticmethod
    def get_prefix_map() -> dict:
        return {
            "vif": "http://usb.org/VendorInfoFile.xsd",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "opt": "http://usb.org/VendorInfoFileOptionalContent.xsd",
        }

    @staticmethod
    def load_input_vif(in_vif: str) -> ET:
        try:
            # Initalizing parser outside the call helps parse all "utf-8" characters (done specifically for the registered trademark character)
            parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True), encoding='utf-8')
            return ET.parse(
                in_vif, parser=parser
            )
        except Exception as e:
            error = (
                "Error: Invalid Input USBIF VIF XML file "
                "provided at path: {}. {}".format(in_vif, e)
            )
            logging.error(error)
            raise InvalidInputVIF(error)

    @staticmethod
    def load_dpam_settings(settings: str) -> ET:
        try:
            parser = ET.XMLParser(target = ET.TreeBuilder(insert_comments=True), encoding='utf-8')
            return ET.parse(
                settings, parser=parser
            )
        except Exception as e:
            error = (
                "Error: Invalid DPAM Settings XML file provided at path: {}. {}".format(
                    settings, e
                )
            )
            logging.error(error)
            raise InvalidSettingsXML(error)

    @staticmethod
    def elements_equal(e1, e2):
        #Check if the contents of two elements are exactly the same
        if e1.tag != e2.tag: return False
        if e1.text != e2.text: return False
        if e1.tail != e2.tail: return False
        if e1.attrib != e2.attrib: return False
        if len(e1) != len(e2): return False
        return all(DPAMVIFGenerator.elements_equal(c1, c2) for c1, c2 in zip(e1, e2))
    
    @staticmethod
    def contains_contents(obj1, obj2):
        # Check if tags are the same
        if obj1.tag != obj2.tag:
            return False

        # Check if obj2 is a direct child of obj1
        if obj2 in obj1:
            return True

        # Check if obj2 is a subset of any child of obj1
        for child in obj1:
            if child.tag == '{http://usb.org/VendorInfoFileOptionalContent.xsd}OptionalContent':

                if DPAMVIFGenerator.contains_contents(child, obj2):
                    return True
                else:
                    xml_string1 = ET.tostring(child, encoding='unicode', method='xml')
                    xml_string2 = ET.tostring(obj2, encoding='unicode', method='xml')

                    # Split the strings into lines
                    lines1 = xml_string1.splitlines()
                    lines2 = xml_string2.splitlines()

                    # Strip leading/trailing whitespace from each line
                    lines1 = [line.strip() for line in lines1]
                    lines2 = [line.strip() for line in lines2]

                    return lines1 == lines2

        return False

    @staticmethod
    def generate_dpam_vif(input_vif: ET, dpam_settings: ET):
        # Get port DPAM settings from DPAM Settings XML
        port_settings = DPAMVIFGenerator.get_port_settings_from_vif(dpam_settings)

        # Insert DPAM Opt Content blocks on each port
        prefix_map = DPAMVIFGenerator.get_prefix_map()

        for port in input_vif.getroot().findall(".//vif:Component", prefix_map):

            #Getting port_name element from the file
            port_name = port.find("vif:Port_Label", prefix_map)

            # Check for existing optional content
            optional_content = port.find("opt:OptionalContent", prefix_map)

            # If both OptionalContent and Port_Name exist
            if optional_content and port_name != None:

                if(not DPAMVIFGenerator.contains_contents(optional_content, port_settings[port_name.text])):
                    # Merge DPAM opt content since OptionalContent block already exists
                    port.remove(optional_content)
                    port.append(port_settings[port_name.text])
            else:
                
                # Optional Content not found
                if port_name != None:
                    port.append(ET.Comment("Non-USB Content"))
                    port.append(port_settings[port_name.text])

                # No Port Name Found
                else:
                    # If Optional Content is None, just add the Optional Content as is
                    if(optional_content is None):
                        port.append(ET.Comment("Non-USB Content"))
                        port.append(port_settings['NA'])

                    # Optional Content already exists and
                    elif(optional_content is not None and not DPAMVIFGenerator.elements_equal(optional_content, port_settings["NA"])):
                        port.remove(optional_content)
                        port.append(port_settings['NA'])
                    else:
                        logging.info('Same OptionalContent already found in the VIF')

    @staticmethod
    def get_port_settings_from_vif(dpam_settings: ET) -> dict[str, ET.Element]:
        # Get port DPAM settings from DPAM Settings XML
        prefix_map = DPAMVIFGenerator.get_prefix_map()
        port_settings: dict[str, ET.Element] = {}
        for port in dpam_settings.getroot().findall(".//vif:Component", prefix_map):
            
            port_data = port.find("vif:Port_Label", prefix_map)

            if(port_data != None):
                port_name = port_data.text
                port_settings[port_name] = port.find(".//opt:OptionalContent", prefix_map)
            else:
                # If no port is found we still associate the settings to a "NA" port_name to still go through with generating a DPAM VIF File.
                port_settings['NA'] = port.find(".//opt:OptionalContent", prefix_map)
        return port_settings

    @staticmethod
    def write_output_vif(generated_vif: ET, out_vif: str):
        ET.indent(generated_vif, space=XML_INDENT, level=0)
        generated_vif.write(out_vif, encoding="utf8", method="xml")


def main(**kwargs):
    # Generate DPAM VIF XML
    generator = DPAMVIFGenerator(**kwargs)
    generator.generate_vif()
