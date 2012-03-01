message CheckSignature {
    required string hostname = 1;
    required string signed_data = 2;
    required bytes signature = 3;
    optional string algorithm = 4;
}

message CheckSignatureWithCert {
    required string cert = 1;
    required string signed_data = 2;
    required bytes signature = 3;
    optional string algorithm = 4;
}

message Response {
    optional string error = 1;
    optional bool value = 2;
}
