# -*- coding: utf-8 -*-
import re
import os
import xml.etree.ElementTree as ET
from ..base import WithRequester


class WebDAV(WithRequester):
    API_URL = "/remote.php/dav/files"

    def __init__(self, *args, **kwargs):
        super(WebDAV, self).__init__(*args)
        self.json_output = kwargs.get("json_output")

    def list_folders(self, uid, path=None, depth=1, all_properties=False):
        """
        Get path files list with files properties for given user, with given depth
        Args:
            uid (str): uid of user
            path (str/None): files path
            depth (int): depth of listing files (directories content for example)
            all_properties (bool): list all available file properties in Nextcloud
        Returns:
            list of dicts if json_output
            list of File objects if not json_output
        """
        if all_properties:
            data = """<?xml version="1.0"?>
                <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"
                            xmlns:nc="http://nextcloud.org/ns">
                  <d:prop>
                        <d:getlastmodified />
                        <d:getetag />
                        <d:getcontenttype />
                        <d:resourcetype />
                        <oc:fileid />
                        <oc:permissions />
                        <oc:size />
                        <d:getcontentlength />
                        <nc:has-preview />
                        <oc:favorite />
                        <oc:comments-unread />
                        <oc:owner-display-name />
                        <oc:share-types />
                  </d:prop>
                </d:propfind>
            """
        else:
            data = None
        additional_url = uid
        if path:
            additional_url = "{}/{}".format(additional_url, path)
        resp = self.requester.propfind(
            additional_url=additional_url, headers={"Depth": str(depth)}, data=data
        )
        if not resp.is_ok:
            resp.data = None
            return resp
        response_data = resp.data
        response_xml_data = ET.fromstring(response_data)
        files_data = [File(single_file) for single_file in response_xml_data]
        resp.data = (
            files_data
            if not self.json_output
            else [each.as_dict() for each in files_data]
        )
        return resp

    def download_file(self, uid, path):
        """
        Download file of given user by path
        File will be saved to working directory
        path argument must be valid file path
        Exception will be raised if:
            path doesn't exist
            path is a directory
            file with same name already exists in working directory
        Args:
            uid (str): uid of user
            path (str): file path
        Returns:
            None
        """
        additional_url = "/".join([uid, path])
        filename = path.split("/")[-1] if "/" in path else path
        file_data = self.list_folders(uid=uid, path=path, depth=0)
        if not file_data:
            raise ValueError("Given path doesn't exist")
        file_resource_type = (
            file_data.data[0].get("resource_type")
            if self.json_output
            else file_data.data[0].resource_type
        )
        if file_resource_type == File.COLLECTION_RESOURCE_TYPE:
            raise ValueError("This is a collection, please specify file path")
        if filename in os.listdir("./"):
            raise ValueError("File with such name already exists in this directory")
        res = self.requester.download(additional_url)
        with open(filename, "wb") as f:
            f.write(res.data)

    def upload_file(self, uid, local_filepath, remote_filepath):
        """
        Upload file to Nextcloud storage
        Args:
            uid (str): uid of user
            local_filepath (str): path to file on local storage
            remote_filepath (str): path where to upload file on Nextcloud storage
        Returns:
        """
        with open(local_filepath, "rb") as f:
            file_content = f.read()
        additional_url = "/".join([uid, remote_filepath])
        return self.requester.put(additional_url, data=file_content)

    def create_folder(self, uid, folder_path):
        """
        Create folder on Nextcloud storage
        Args:
            uid (str): uid of user
            folder_path (str): folder path
        Returns:
        """
        return self.requester.make_collection(
            additional_url="/".join([uid, folder_path])
        )

    def delete_path(self, uid, path):
        """
        Delete file or folder with all content of given user by path
        Args:
            uid (str): uid of user
            path (str): file or folder path to delete
        Returns:
        """
        url = "/".join([uid, path])
        return self.requester.delete(url=url)

    def move_path(self, uid, path, destination_path, overwrite=False):
        """
        Move file or folder to destination
        Args:
            uid (str): uid of user
            path (str): file or folder path to move
            destionation_path (str): destination where to move
            overwrite (bool): allow destination path overriding
        Returns:
        """
        path_url = "/".join([uid, path])
        destination_path_url = "/".join([uid, destination_path])
        return self.requester.move(
            url=path_url, destination=destination_path_url, overwrite=overwrite
        )

    def copy_path(self, uid, path, destination_path, overwrite=False):
        """
        Copy file or folder to destination
        Args:
            uid (str): uid of user
            path (str): file or folder path to copy
            destionation_path (str): destination where to copy
            overwrite (bool): allow destination path overriding
        Returns:
        """
        path_url = "/".join([uid, path])
        destination_path_url = "/".join([uid, destination_path])
        return self.requester.copy(
            url=path_url, destination=destination_path_url, overwrite=overwrite
        )

    def set_favorites(self, uid, path):
        """
        Set files of a user favorite
        Args:
            uid (str): uid of user
            path (str): file or folder path to make favorite
        Returns:
        """
        data = """<?xml version="1.0"?>
        <d:propertyupdate xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
          <d:set>
                <d:prop>
                  <oc:favorite>1</oc:favorite>
                </d:prop>
          </d:set>
        </d:propertyupdate>
        """
        url = "/".join([uid, path])
        return self.requester.proppatch(additional_url=url, data=data)

    def list_favorites(self, uid, path=""):
        """
        Set files of a user favorite
        Args:
            uid (str): uid of user
            path (str): file or folder path to make favorite
        Returns:
        """
        data = """<?xml version="1.0"?>
        <oc:filter-files xmlns:d="DAV:"
                         xmlns:oc="http://owncloud.org/ns"
                         xmlns:nc="http://nextcloud.org/ns">
                 <oc:filter-rules>
                         <oc:favorite>1</oc:favorite>
                 </oc:filter-rules>
         </oc:filter-files>
        """
        url = "/".join([uid, path])
        res = self.requester.report(additional_url=url, data=data)
        if not res.is_ok:
            res.data = None
            return res
        response_xml_data = ET.fromstring(res.data)
        files_data = [File(single_file) for single_file in response_xml_data]
        res.data = (
            files_data
            if not self.json_output
            else [each.as_dict() for each in files_data]
        )
        return res


class File(object):
    SUCCESS_STATUS = "HTTP/1.1 200 OK"

    # key is NextCloud property, value is python variable name
    FILE_PROPERTIES = {
        # d:
        "getlastmodified": "last_modified",
        "getetag": "etag",
        "getcontenttype": "content_type",
        "resourcetype": "resource_type",
        "getcontentlength": "content_length",
        # oc:
        "id": "id",
        "fileid": "file_id",
        "favorite": "favorite",
        "comments-href": "comments_href",
        "comments-count": "comments_count",
        "comments-unread": "comments_unread",
        "owner-id": "owner_id",
        "owner-display-name": "owner_display_name",
        "share-types": "share_types",
        "checksums": "check_sums",
        "size": "size",
        "href": "href",
        # nc:
        "has-preview": "has_preview",
    }
    xml_namespaces_map = {
        "d": "DAV:",
        "oc": "http://owncloud.org/ns",
        "nc": "http://nextcloud.org/ns",
    }
    COLLECTION_RESOURCE_TYPE = "collection"

    def __init__(self, xml_data):
        self.href = xml_data.find("d:href", self.xml_namespaces_map).text
        for propstat in xml_data.iter("{DAV:}propstat"):
            if (
                propstat.find("d:status", self.xml_namespaces_map).text
                != self.SUCCESS_STATUS
            ):
                continue
            for file_property in propstat.find("d:prop", self.xml_namespaces_map):
                file_property_name = re.sub("{.*}", "", file_property.tag)
                if file_property_name not in self.FILE_PROPERTIES:
                    continue
                if file_property_name == "resourcetype":
                    value = self._extract_resource_type(file_property)
                else:
                    value = file_property.text
                setattr(self, self.FILE_PROPERTIES[file_property_name], value)

    def _extract_resource_type(self, file_property):
        file_type = list(file_property)
        if file_type:
            return re.sub("{.*}", "", file_type[0].tag)
        return None

    def as_dict(self):
        return {
            key: value
            for key, value in self.__dict__.items()
            if key in self.FILE_PROPERTIES.values()
        }


class WebDAVStatusCodes(object):
    CREATED_CODE = 201
    NO_CONTENT_CODE = 204
    MULTISTATUS_CODE = 207
    ALREADY_EXISTS_CODE = 405
    PRECONDITION_FAILED_CODE = 412
