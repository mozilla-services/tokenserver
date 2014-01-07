if [ -e "/opt/local/include/libmemcached/memcached.h" ]
then
    LIBMEMCACHED=/opt/local/ bin/pip install pylibmc==1.2.3
else
    bin/pip install pylibmc==1.2.3
fi
