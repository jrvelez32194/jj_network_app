import logging
import socket
from routeros_api import RouterOsApiPool, exceptions as ros_exceptions

logger = logging.getLogger("mikrotik")


class MikroTikClient:
    def __init__(self, host, username, password, port=8728):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.api_pool = None
        self.client = None

    # ===================================
    # 🧠 Connection handling
    # ===================================
    def connect(self) -> bool:
        """Establish a connection to the MikroTik router. Returns True if connected."""

        # Close old pool if still open
        if self.api_pool:
            try:
                self.api_pool.disconnect()
            except Exception:
                pass
            self.api_pool = None
            self.client = None

        try:
            # Quick TCP connectivity test first
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(3)
                sock.connect((self.host, self.port))
            logger.debug(f"🔌 TCP port {self.port} reachable on {self.host}")

            # Initialize API pool
            self.api_pool = RouterOsApiPool(
                self.host,
                username=self.username,
                password=self.password,
                port=self.port,
                plaintext_login=True,
            )
            self.client = self.api_pool.get_api()
            logger.info(f"✅ Connected to MikroTik {self.host}")
            return True

        except socket.timeout:
            logger.warning(f"⏱️ Timeout connecting to {self.host}:{self.port}")
        except ConnectionRefusedError:
            logger.warning(f"🚫 Connection refused by {self.host}:{self.port}")
        except ros_exceptions.RouterOsApiConnectionError as e:
            logger.warning(f"❌ RouterOS API error: {e}")
        except Exception as e:
            logger.warning(f"💥 Unexpected error connecting to {self.host}: {e}")

        self.client = None
        return False

    def ensure_connection(self) -> bool:
        """Ensure the API connection is active, reconnect if needed. Returns True if connected."""
        if not self.client:
            return self.connect()

        try:
            identity = self.client.get_resource('/system/identity').get()
            if not identity:
                raise Exception("Empty response from RouterOS")
            return True
        except Exception as e:
            logger.warning(f"⚠️ MikroTik connection lost, reconnecting... ({e})")
            return self.connect()

    # ===================================
    # 🚀 Netwatch
    # ===================================
    def get_netwatch(self):
        if not self.ensure_connection():
            return []
        try:
            netwatch = self.client.get_resource('/tool/netwatch')
            rules = netwatch.get()
            return [
                {
                    "host": r.get("host"),
                    "comment": r.get("comment", ""),
                    "status": r.get("status", "").upper(),
                }
                for r in rules
            ]
        except Exception as e:
            logger.error(f"❌ Failed to fetch Netwatch rules: {e}")
            return []

    # ===================================
    # 🚀 Speed control
    # ===================================
    def set_speed_limit(self, queue_name: str, speed_limit: str):
        """Set or remove speed limit for a given queue using routeros-api."""
        if not self.ensure_connection():
            return False

        queues = self.client.get_resource('/queue/simple')
        try:
            qlist = queues.get(name=queue_name)
            if not qlist:
                logger.warning(f"⚠️ No queue found with name={queue_name}")
                return False
            queue = qlist[0]

            # Determine max-limit value
            if not speed_limit or speed_limit.lower() in ["unlimited", "normal", "default"]:
                max_limit = "0/0"
                readable = "unlimited"
            else:
                if "/" not in speed_limit:
                    max_limit = f"{speed_limit}/{speed_limit}"
                else:
                    max_limit = speed_limit
                readable = max_limit

            # 🔑 routeros-api expects "id" (not ".id")
            queues.set(id=queue["id"], **{"max-limit": max_limit})
            logger.info(
                f"✅ Applied max-limit={readable} for queue '{queue_name}' (id={queue['id']})"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Error setting speed limit for {queue_name}: {e}")
            return False

    # ===================================
    # 🔒 Firewall controls
    # ===================================
    def block_client(self, comment: str):
        """Enable firewall address-list entry by matching comment."""
        if not self.ensure_connection():
            return False
        try:
            addr_list = self.client.get_resource('/ip/firewall/address-list')
            entries = addr_list.get(comment=comment)
            if not entries:
                logger.warning(f"⚠️ No address-list entry found with comment={comment}")
                return False

            for entry in entries:
                addr_list.set(id=entry["id"], disabled="no")
                logger.info(f"✅ Enabled address-list entry {entry['id']} for {comment}")
            return True

        except Exception as e:
            logger.error(f"❌ Error enabling address-list entry for {comment}: {e}")
            return False

    def unblock_client(self, comment: str):
        """Disable firewall address-list entry by matching comment."""
        if not self.ensure_connection():
            return False
        try:
            addr_list = self.client.get_resource('/ip/firewall/address-list')
            entries = addr_list.get(comment=comment)
            if not entries:
                logger.warning(f"⚠️ No address-list entry found with comment={comment}")
                return False

            for entry in entries:
                addr_list.set(id=entry["id"], disabled="yes")
                logger.info(f"✅ Disabled address-list entry {entry['id']} for {comment}")
            return True

        except Exception as e:
            logger.error(f"❌ Error disabling address-list entry for {comment}: {e}")
            return False
