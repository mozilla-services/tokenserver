%define pyver 26
%define name python%{pyver}-tokenserver
%define pythonname tokenserver
%define version 0.1
%define release 1

Summary: Token Server.
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{pythonname}-%{version}.tar.gz
License: MPL
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{pythonname}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Tarek Ziade <tarek@mozilla.com>
Requires: python26-m2crypto nginx memcached gunicorn python%{pyver} python%{pyver}-setuptools python%{pyver}-webob python%{pyver}-paste python%{pyver}-pastedeploy python%{pyver}-sqlalchemy python%{pyver}-mako python%{pyver}-simplejson python%{pyver}-pastescript python%{pyver}-mako python%{pyver}-markupsafe python%{pyver}-chameleon python%{pyver}-jinja2 python%{pyver}-pyramid python%{pyver}-pyramid_jinja2 python%{pyver}-pyramid_debugtoolbar python%{pyver}-repoze.lru python%{pyver}-translationstring python%{pyver}-wsgi_intercept python%{pyver}-zope.component python%{pyver}-zope.deprecation python%{pyver}-zope.event python%{pyver}-zope.interface python%{pyver}-venusian

Url: https://github.com/mozilla/tokenserver

%description
Token Server.


%prep
%setup -n %{pythonname}-%{version} -n %{pythonname}-%{version}

%build
python%{pyver} setup.py build

%install

# the config files for Sync apps
mkdir -p %{buildroot}%{_sysconfdir}/tokenserver
install -m 0644 etc/tokenserver-prod.ini %{buildroot}%{_sysconfdir}/tokenserver/tokenserver-prod.ini

# nginx config
mkdir -p %{buildroot}%{_sysconfdir}/nginx
mkdir -p %{buildroot}%{_sysconfdir}/nginx/conf.d
install -m 0644 etc/tokenserver.nginx.conf %{buildroot}%{_sysconfdir}/nginx/conf.d/tokenserver.conf

# logging
mkdir -p %{buildroot}%{_localstatedir}/log
touch %{buildroot}%{_localstatedir}/log/tokenserver.log

# the app
python%{pyver} setup.py install --single-version-externally-managed --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%post
touch %{_localstatedir}/log/tokenserver.log
chown nginx:nginx %{_localstatedir}/log/tokenserver.log
chmod 640 %{_localstatedir}/log/tokenserver.log

%files -f INSTALLED_FILES

%attr(640, nginx, nginx) %ghost %{_localstatedir}/log/tokenserver.log

%dir %{_sysconfdir}/tokenserver/

%config(noreplace) %{_sysconfdir}/tokenserver/*
%config(noreplace) %{_sysconfdir}/nginx/conf.d/tokenserver.conf

%defattr(-,root,root)
