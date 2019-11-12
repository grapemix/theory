import sys
from theory.thevent import gevent
import weakref

from theory.utils.six.moves import xrange

if sys.version_info < (3, 4):
  from .weakrefBackports import WeakMethod
else:
  from weakref import WeakMethod


def _makeId(target):
  if hasattr(target, '__func__'):
    return (id(target.__self__), id(target.__func__))
  return id(target)
NONE_ID = _makeId(None)

# A marker for caching
NO_RECEIVERS = object()


class Signal(object):
  """
  Base class for all signals

  Internal attributes:

    receivers
      { receiverkey (id) : weakref(receiver) }
  """
  def __init__(self, providingArgs=None, useCaching=False):
    """
    Create a new signal.

    providingArgs
      A list of the arguments this signal can pass along in a send() call.
    """
    self.receivers = []
    if providingArgs is None:
      providingArgs = []
    self.providingArgs = set(providingArgs)
    self.lock = gevent.threading.Lock()
    self.useCaching = useCaching
    # For convenience we create empty caches even if they are not used.
    # A note about caching: if useCaching is defined, then for each
    # distinct sender we cache the receivers that sender has in
    # 'senderReceiversCache'. The cache is cleaned when .connect() or
    # .disconnect() is called and populated on send().
    self.senderReceiversCache = weakref.WeakKeyDictionary() if useCaching else {}
    self._deadReceivers = False

  def connect(self, receiver, sender=None, weak=True, dispatchUid=None):
    """
    Connect receiver to sender for signal.

    Arguments:

      receiver
        A function or an instance method which is to receive signals.
        Receivers must be hashable objects.

        If weak is True, then receiver must be weak-referencable.

        Receivers must be able to accept keyword arguments.

        If receivers have a dispatchUid attribute, the receiver will
        not be added if another receiver already exists with that
        dispatchUid.

      sender
        The sender to which the receiver should respond. Must either be
        of type Signal, or None to receive events from any sender.

      weak
        Whether to use weak references to the receiver. By default, the
        module will attempt to use weak references to the receiver
        objects. If this parameter is false, then strong references will
        be used.

      dispatchUid
        An identifier used to uniquely identify a particular instance of
        a receiver. This will usually be a string, though it may be
        anything hashable.
    """
    from theory.conf import settings

    # If DEBUG is on, check that we got a good receiver
    if settings.configured and settings.DEBUG:
      import inspect
      assert callable(receiver), "Signal receivers must be callable."

      # Check for **kwargs
      # Not all callables are inspectable with getargspec, so we'll
      # try a couple different ways but in the end fall back on assuming
      # it is -- we don't want to prevent registration of valid but weird
      # callables.
      try:
        argspec = inspect.getargspec(receiver)
      except TypeError:
        try:
          argspec = inspect.getargspec(receiver.__call__)
        except (TypeError, AttributeError):
          argspec = None
      if argspec:
        assert argspec[2] is not None, \
          "Signal receivers must accept keyword arguments (**kwargs)."

    if dispatchUid:
      lookupKey = (dispatchUid, _makeId(sender))
    else:
      lookupKey = (_makeId(receiver), _makeId(sender))

    if weak:
      ref = weakref.ref
      receiverObject = receiver
      # Check for bound methods
      if hasattr(receiver, '__self__') and hasattr(receiver, '__func__'):
        ref = WeakMethod
        receiverObject = receiver.__self__
      if sys.version_info >= (3, 4):
        receiver = ref(receiver)
        weakref.finalize(receiverObject, self._removeReceiver)
      else:
        receiver = ref(receiver, self._removeReceiver)

    with self.lock:
      self._clearDeadReceivers()
      for rKey, _ in self.receivers:
        if rKey == lookupKey:
          break
      else:
        self.receivers.append((lookupKey, receiver))
      self.senderReceiversCache.clear()

  def disconnect(self, receiver=None, sender=None, weak=True, dispatchUid=None):
    """
    Disconnect receiver from sender for signal.

    If weak references are used, disconnect need not be called. The receiver
    will be remove from dispatch automatically.

    Arguments:

      receiver
        The registered receiver to disconnect. May be none if
        dispatchUid is specified.

      sender
        The registered sender to disconnect

      weak
        The weakref state to disconnect

      dispatchUid
        the unique identifier of the receiver to disconnect
    """
    if dispatchUid:
      lookupKey = (dispatchUid, _makeId(sender))
    else:
      lookupKey = (_makeId(receiver), _makeId(sender))

    with self.lock:
      self._clearDeadReceivers()
      for index in xrange(len(self.receivers)):
        (rKey, _) = self.receivers[index]
        if rKey == lookupKey:
          del self.receivers[index]
          break
      self.senderReceiversCache.clear()

  def hasListeners(self, sender=None):
    return bool(self._liveReceivers(sender))

  def send(self, sender, **named):
    """
    Send signal from sender to all connected receivers.

    If any receiver raises an error, the error propagates back through send,
    terminating the dispatch loop, so it is quite possible to not have all
    receivers called if a raises an error.

    Arguments:

      sender
        The sender of the signal Either a specific object or None.

      named
        Named arguments which will be passed to receivers.

    Returns a list of tuple pairs [(receiver, response), ... ].
    """
    responses = []
    if not self.receivers or self.senderReceiversCache.get(sender) is NO_RECEIVERS:
      return responses

    for receiver in self._liveReceivers(sender):
      response = receiver(signal=self, sender=sender, **named)
      responses.append((receiver, response))
    return responses

  def sendRobust(self, sender, **named):
    """
    Send signal from sender to all connected receivers catching errors.

    Arguments:

      sender
        The sender of the signal. Can be any python object (normally one
        registered with a connect if you actually want something to
        occur).

      named
        Named arguments which will be passed to receivers. These
        arguments must be a subset of the argument names defined in
        providingArgs.

    Return a list of tuple pairs [(receiver, response), ... ]. May raise
    DispatcherKeyError.

    If any receiver raises an error (specifically any subclass of
    Exception), the error instance is returned as the result for that
    receiver. The traceback is always attached to the error at
    ``__traceback__``.
    """
    responses = []
    if not self.receivers or self.senderReceiversCache.get(sender) is NO_RECEIVERS:
      return responses

    # Call each receiver with whatever arguments it can accept.
    # Return a list of tuple pairs [(receiver, response), ... ].
    for receiver in self._liveReceivers(sender):
      try:
        response = receiver(signal=self, sender=sender, **named)
      except Exception as err:
        if not hasattr(err, '__traceback__'):
          err.__traceback__ = sys.excInfo()[2]
        responses.append((receiver, err))
      else:
        responses.append((receiver, response))
    return responses

  def _clearDeadReceivers(self):
    # Note: caller is assumed to hold self.lock.
    if self._deadReceivers:
      self._deadReceivers = False
      newReceivers = []
      for r in self.receivers:
        if isinstance(r[1], weakref.ReferenceType) and r[1]() is None:
          continue
        newReceivers.append(r)
      self.receivers = newReceivers

  def _liveReceivers(self, sender):
    """
    Filter sequence of receivers to get resolved, live receivers.

    This checks for weak references and resolves them, then returning only
    live receivers.
    """
    receivers = None
    if self.useCaching and not self._deadReceivers:
      receivers = self.senderReceiversCache.get(sender)
      # We could end up here with NO_RECEIVERS even if we do check this case in
      # .send() prior to calling _liveReceivers() due to concurrent .send() call.
      if receivers is NO_RECEIVERS:
        return []
    if receivers is None:
      with self.lock:
        self._clearDeadReceivers()
        senderkey = _makeId(sender)
        receivers = []
        for (receiverkey, rSenderkey), receiver in self.receivers:
          if rSenderkey == NONE_ID or rSenderkey == senderkey:
            receivers.append(receiver)
        if self.useCaching:
          if not receivers:
            self.senderReceiversCache[sender] = NO_RECEIVERS
          else:
            # Note, we must cache the weakref versions.
            self.senderReceiversCache[sender] = receivers
    nonWeakReceivers = []
    for receiver in receivers:
      if isinstance(receiver, weakref.ReferenceType):
        # Dereference the weak reference.
        receiver = receiver()
        if receiver is not None:
          nonWeakReceivers.append(receiver)
      else:
        nonWeakReceivers.append(receiver)
    return nonWeakReceivers

  def _removeReceiver(self, receiver=None):
    # Mark that the self.receivers list has dead weakrefs. If so, we will
    # clean those up in connect, disconnect and _liveReceivers while
    # holding self.lock. Note that doing the cleanup here isn't a good
    # idea, _removeReceiver() will be called as side effect of garbage
    # collection, and so the call can happen while we are already holding
    # self.lock.
    self._deadReceivers = True


def receiver(signal, **kwargs):
  """
  A decorator for connecting receivers to signals. Used by passing in the
  signal (or list of signals) and keyword arguments to connect::

    @receiver(postSave, sender=MyModel)
    def signalReceiver(sender, **kwargs):
      ...

    @receiver([postSave, postDelete], sender=MyModel)
    def signalsReceiver(sender, **kwargs):
      ...

  """
  def _decorator(func):
    if isinstance(signal, (list, tuple)):
      for s in signal:
        s.connect(func, **kwargs)
    else:
      signal.connect(func, **kwargs)
    return func
  return _decorator
