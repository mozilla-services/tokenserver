if [ -e "/opt/local/include/libmemcached/memcached.h" ]
then
    LIBMEMCACHED=/opt/local/ bin/pip install pylibmc==1.2.2
else
    bin/pip install pylibmc==1.2.2
fi
