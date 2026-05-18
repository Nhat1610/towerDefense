"""
algorithms/linked_list.py
=========================
EntityLinkedList — a doubly-linked list for managing game entities
(enemies, projectiles, particles).

IT003 ASSIGNMENT: Implement every method marked with
    raise NotImplementedError(...)
The docstring above each method describes the expected behaviour.

Do NOT change the public interface (method names / parameters).
The renderer and game loop depend on iteration order and the
ability to remove nodes mid-iteration via `remove_node`.
"""

from __future__ import annotations
from typing import Any, Iterator, Optional


class Node:
    """A single node in the doubly-linked list."""

    def __init__(self, data: Any) -> None:
        self.data: Any = data
        self.prev: Optional[Node] = None
        self.next: Optional[Node] = None

    def __repr__(self) -> str:
        return f"Node({self.data!r})"


class EntityLinkedList:


    def __init__(self) -> None:
        self._head: Optional[Node] = None
        self._tail: Optional[Node] = None
        self._size: int = 0

    # ── Core operations ────────────────────────────────────────────────────

    def append(self, data: Any) -> Node:

        newNode = Node(data)
        if not self._size:
            self._head = newNode
            self._tail = newNode
        else:
            curTail = self._tail
            self._tail.next = newNode
            self._tail = self._tail.next
            self._tail.prev = curTail
        self._size += 1
        

    def prepend(self, data: Any) -> Node:

        newNode = Node(data)
        if not self._size:
            self._head = newNode
            self._tail = newNode
        else:
            curHead = self._head
            self._head.prev = newNode
            self._head = newNode
            self._head.next = curHead
        self._size += 1
        

    def remove_node(self, node: Node) -> None:

        if node.prev:
            node.prev.next = node.next
        else:
            self._head = node.next
        
        if node.next:
            node.next.prev = node.prev
        else:
            self._tail = node.prev
        node.prev = None
        node.next = None
        self._size -= 1
    def remove_data(self, data: Any) -> bool:

        for node in self._iter_nodes():
            if node.data == data:
                self.remove_node(node)
                return True
        return False

       
    def clear(self) -> None:
        self._head = None
        self._tail = None
        self._size = None

    # ── Query ──────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._size > 0

    def __iter__(self) -> Iterator[Any]:

        snp = list(self._iter_nodes())
        for node in snp:
            yield node.data

    def __repr__(self) -> str:
        items = [repr(n) for n in self._iter_nodes()]
        return f"EntityLinkedList([{', '.join(items)}])"

    # ── Internal helpers (you may use these in your implementation) ────────

    def _iter_nodes(self) -> Iterator[Node]:
        """Yield raw Node objects head → tail (helper for __repr__ etc.)."""
        current = self._head
        while current is not None:
            yield current
            current = current.next

    @property
    def head(self) -> Optional[Node]:
        return self._head

    @property
    def tail(self) -> Optional[Node]:
        return self._tail
