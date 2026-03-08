class Node:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.size = 0
        self.cache = dict()
        self.head, self.tail = Node(0, 0), Node(0, 0)
        self._initialize_list()

    def _initialize_list(self):
        self.head.next = self.tail
        self.tail.prev = self.head

    def _add_to_head(self, node: Node):
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def _remove_node(self, node: Node):
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _move_to_head(self, node: Node):
        self._remove_node(node)
        self._add_to_head(node)

    def _pop_tail(self) -> Node:
        if self.size == 0:
            return None
        node = self.tail.prev
        if node == self.head:
            return None
        self._remove_node(node)
        return node

    def get(self, key: int) -> int:
        if key in self.cache:
            node = self.cache[key]
            self._move_to_head(node)
            return node.value
        return -1

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_head(node)
            return
        
        node = Node(key, value)
        self.cache[key] = node
        self._add_to_head(node)
        self.size += 1
        
        if self.size > self.capacity:
            tail_node = self._pop_tail()
            if tail_node:
                del self.cache[tail_node.key]
                self.size -= 1

    def display(self):
        current = self.head.next
        while current != self.tail:
            print(f"Key: {current.key}, Value: {current.value} -> ", end='')
            current = current.next
        print()