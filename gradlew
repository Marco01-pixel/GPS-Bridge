#!/usr/bin/env bash
APP_BASE_NAME=`basename "$0"`
APP_HOME=`dirname "$0"`
DEFAULT_JVM_OPTS="-Xmx64m"
JAVA_HOME=${JAVA_HOME:-$(dirname $(dirname $(which java)))}
exec "$JAVA_HOME/bin/java" $DEFAULT_JVM_OPTS -cp "$APP_HOME/gradle/wrapper/gradle-wrapper.jar" org.gradle.wrapper.GradleWrapperMain "$@"
